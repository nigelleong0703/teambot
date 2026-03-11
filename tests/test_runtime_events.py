from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from teambot.agent.service import AgentService
from teambot.agent.graph import build_graph
from teambot.contracts.contracts import ModelTextInvocationResult, ModelToolCall, ModelToolInvocationResult
from teambot.domain.models import (
    AgentState,
    InboundEvent,
    OutboundReply,
    ReplyTarget,
    RuntimeEvent,
)
from teambot.memory.models import SessionCompactionResult
from teambot.actions.tools.registry import ToolManifest, ToolRegistry


def test_runtime_event_supports_agent_transcript_shapes() -> None:
    event = RuntimeEvent(
        run_id="run-1",
        step=2,
        event_type="tool_call",
        text="Need current time",
        action_name="get_current_time",
        action_input={"timezone": "Asia/Kuala_Lumpur"},
    )

    assert event.run_id == "run-1"
    assert event.step == 2
    assert event.event_type == "tool_call"
    assert event.action_name == "get_current_time"
    assert event.action_input["timezone"] == "Asia/Kuala_Lumpur"


def test_runtime_event_rejects_unknown_event_type() -> None:
    with pytest.raises(ValueError):
        RuntimeEvent(
            run_id="run-1",
            step=0,
            event_type="unknown",
        )


def test_outbound_reply_contract_remains_compatible() -> None:
    reply = OutboundReply(
        event_id="evt-1",
        conversation_key="T1:C1:1.1",
        reply_target=ReplyTarget(team_id="T1", channel_id="C1", thread_ts="1.1"),
        text="done",
        skill_name="",
    )

    assert reply.text == "done"
    assert reply.execution_trace == []


@dataclass
class _ReasonerStub:
    calls: list[ModelToolInvocationResult | ModelTextInvocationResult]

    def has_role(self, role: str) -> bool:
        return role == "agent_model"

    def invoke_role_tools(
        self,
        *,
        role: str,
        system_prompt: str,
        payload: dict[str, Any],
        tools: list[Any],
    ) -> ModelToolInvocationResult:
        _ = role, system_prompt, payload, tools
        result = self.calls.pop(0)
        assert isinstance(result, ModelToolInvocationResult)
        return result

    def invoke_role_text(
        self,
        *,
        role: str,
        system_prompt: str,
        user_message: str,
    ) -> ModelTextInvocationResult:
        _ = role, system_prompt, user_message
        result = self.calls.pop(0)
        assert isinstance(result, ModelTextInvocationResult)
        return result

    def invoke_role_json(self, **_: Any):
        raise NotImplementedError


def _state(text: str) -> AgentState:
    return {
        "conversation_key": "T1:C1:1",
        "recent_turns": [],
        "conversation_summary": "",
        "memory_system_prompt_suffix": "",
        "event_type": "message",
        "user_text": text,
        "reaction": None,
        "react_step": 0,
        "react_max_steps": 3,
        "react_done": False,
        "react_notes": [],
        "reasoning_note": "",
        "active_skill_names": [],
        "active_skill_docs": [],
        "selected_action": "",
        "selected_skill": "",
        "action_input": {},
        "skill_input": {},
        "action_output": {},
        "skill_output": {},
        "execution_trace": [],
        "reply_text": "",
    }


def test_graph_emits_runtime_events_for_tool_then_final_turn() -> None:
    events: list[RuntimeEvent] = []
    tools = ToolRegistry()
    tools.register(
        ToolManifest(name="get_current_time", description="time tool"),
        lambda _state: {"message": "2026-03-07 21:30:00"},
    )
    reasoner = _ReasonerStub(
        calls=[
            ModelToolInvocationResult(
                text="",
                tool_calls=[
                    ModelToolCall(
                        name="get_current_time",
                        arguments={"timezone": "Asia/Kuala_Lumpur"},
                    )
                ],
                provider="stub",
                model="stub-model",
            ),
            ModelToolInvocationResult(
                text="It is 9:30 PM.",
                tool_calls=[],
                provider="stub",
                model="stub-model",
            ),
        ]
    )

    graph = build_graph(
        tool_registry=tools,
        planner=reasoner,
        runtime_event_listener=events.append,
    )

    result = graph.invoke(_state("what time is it"))

    assert result["reply_text"] == "It is 9:30 PM."
    assert [event.event_type for event in events] == [
        "tool_call",
        "tool_result",
        "final_text",
        "run_completed",
    ]
    assert events[0].action_name == "get_current_time"
    assert events[1].observation == "2026-03-07 21:30:00"


def test_tools_question_still_goes_through_reasoner() -> None:
    tools = ToolRegistry()
    tools.register(
        ToolManifest(name="read_file", description="Read files"),
        lambda _state: {"message": "ok"},
    )
    reasoner = _ReasonerStub(
        calls=[
            ModelToolInvocationResult(
                text="I can help with file work and other enabled capabilities when needed.",
                tool_calls=[],
                provider="stub",
                model="stub-model",
            ),
        ]
    )

    graph = build_graph(
        tool_registry=tools,
        planner=reasoner,
    )

    result = graph.invoke(_state("what tools do you have"))

    assert result["reply_text"] == "I can help with file work and other enabled capabilities when needed."
    assert result["reasoning_note"] == "Reasoner route: final answer"


@pytest.mark.asyncio
async def test_agent_service_stream_event_yields_runtime_events_and_persists_reply() -> None:
    service = AgentService(tools_profile="minimal")
    event = InboundEvent(
        event_id="evt-stream-1",
        event_type="message",
        team_id="T1",
        channel_id="C1",
        thread_ts="1.1",
        user_id="U1",
        text="hello",
    )

    events = [item async for item in service.stream_event(event)]

    assert events
    assert events[-1].event_type == "run_completed"

    cached = await service.process_event(event)
    assert cached.text == events[-1].text


@pytest.mark.asyncio
async def test_agent_service_stream_event_maps_provider_tokens_to_runtime_deltas() -> None:
    service = AgentService(tools_profile="minimal")
    event = InboundEvent(
        event_id="evt-stream-2",
        event_type="message",
        team_id="T1",
        channel_id="C1",
        thread_ts="1.2",
        user_id="U1",
        text="stream please",
    )

    provider_events: list[tuple[str, dict[str, Any]]] = []

    class _ProviderStub:
        def __init__(self) -> None:
            self._event_listener = None

        def set_event_listener(self, listener):
            self._event_listener = listener

    provider_stub = _ProviderStub()
    service.provider_manager = provider_stub  # type: ignore[assignment]

    def _invoke_stub(state: AgentState, runtime_event_listener=None):
        assert runtime_event_listener is not None
        if provider_stub._event_listener is not None:
            provider_stub._event_listener("model_reasoning_token", {"token": "Need"})
            provider_stub._event_listener("model_token", {"token": "Done"})
        runtime_event_listener(RuntimeEvent(run_id=state["conversation_key"], step=1, event_type="thinking", text="Need"))
        runtime_event_listener(RuntimeEvent(run_id=state["conversation_key"], step=1, event_type="run_completed", text="Done"))
        return {
            **state,
            "reply_text": "Done",
            "selected_action": "",
            "selected_skill": "",
            "reasoning_note": "Need",
            "execution_trace": [],
        }

    service._agent.invoke = _invoke_stub  # type: ignore[method-assign]

    def _previous_listener(name: str, payload: dict[str, Any]) -> None:
        provider_events.append((name, payload))

    provider_stub.set_event_listener(_previous_listener)

    events = [item async for item in service.stream_event(event)]

    assert [item.event_type for item in events] == [
        "thinking_delta",
        "final_delta",
        "thinking",
        "run_completed",
    ]
    assert events[0].text == "Need"
    assert events[1].text == "Done"
    assert provider_events == [
        ("model_reasoning_token", {"token": "Need"}),
        ("model_token", {"token": "Done"}),
    ]


@pytest.mark.asyncio
async def test_agent_service_stream_event_emits_memory_compacted_before_completion() -> None:
    service = AgentService(tools_profile="minimal")
    event = InboundEvent(
        event_id="evt-stream-3",
        event_type="message",
        team_id="T1",
        channel_id="C1",
        thread_ts="1.22",
        user_id="U1",
        text="hello",
    )

    async def _append_turns(**_: Any) -> SessionCompactionResult:
        return SessionCompactionResult(compacted=True, last_compacted_seq=2)

    service.session_memory.append_turns = _append_turns  # type: ignore[method-assign]

    def _invoke_stub(state: AgentState, runtime_event_listener=None):
        assert runtime_event_listener is not None
        runtime_event_listener(
            RuntimeEvent(run_id=state["conversation_key"], step=1, event_type="thinking", text="Need")
        )
        runtime_event_listener(
            RuntimeEvent(run_id=state["conversation_key"], step=1, event_type="run_completed", text="Done")
        )
        return {
            **state,
            "reply_text": "Done",
            "selected_action": "",
            "selected_skill": "",
            "reasoning_note": "Need",
            "execution_trace": [],
        }

    service._agent.invoke = _invoke_stub  # type: ignore[method-assign]

    events = [item async for item in service.stream_event(event)]

    assert [item.event_type for item in events] == [
        "thinking",
        "memory_compacted",
        "run_completed",
    ]


@pytest.mark.asyncio
async def test_agent_service_injects_memory_context_into_state() -> None:
    service = AgentService(tools_profile="minimal")
    first_event = InboundEvent(
        event_id="evt-history-1",
        event_type="message",
        team_id="T1",
        channel_id="C1",
        thread_ts="1.3",
        user_id="U1",
        text="hello there",
    )
    first_reply = await service.process_event(first_event)

    captured_state: dict[str, Any] = {}

    def _invoke_stub(state: AgentState, runtime_event_listener=None):
        _ = runtime_event_listener
        captured_state.update(state)
        return {
            **state,
            "reply_text": "second reply",
            "selected_action": "",
            "selected_skill": "",
            "reasoning_note": "history-aware",
            "execution_trace": [],
        }

    service._agent.invoke = _invoke_stub  # type: ignore[method-assign]

    second_event = InboundEvent(
        event_id="evt-history-2",
        event_type="message",
        team_id="T1",
        channel_id="C1",
        thread_ts="1.3",
        user_id="U1",
        text="follow up",
    )

    reply = await service.process_event(second_event)

    assert reply.text == "second reply"
    assert captured_state["recent_turns"] == [
        {"role": "user", "text": "hello there"},
        {"role": "assistant", "text": " ".join(first_reply.text.split())},
    ]
    assert captured_state["conversation_summary"] == ""
    assert captured_state["memory_system_prompt_suffix"] == ""
