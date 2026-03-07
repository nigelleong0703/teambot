from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from teambot.contracts.contracts import ModelTextInvocationResult, ModelToolCall, ModelToolInvocationResult
from teambot.agent.execution import observe_node
from teambot.agent.graph import build_graph
from teambot.skills.registry import SkillRegistry
from teambot.actions.tools.registry import ToolManifest, ToolRegistry
from teambot.domain.models import AgentState


@dataclass
class _SequentialReasoner:
    rounds: list[dict[str, Any]]
    seen_payloads: list[dict[str, Any]] = field(default_factory=list)

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
        self.seen_payloads.append(payload)
        current = self.rounds.pop(0)
        return ModelToolInvocationResult(
            text=current.get("text", ""),
            tool_calls=current.get("tool_calls", []),
            provider="stub",
            model="stub-model",
        )

    def invoke_role_text(
        self,
        *,
        role: str,
        system_prompt: str,
        user_message: str,
    ) -> ModelTextInvocationResult:
        raise AssertionError("tool-enabled path should use invoke_role_tools")


def _state(text: str = "hi") -> AgentState:
    return {
        "conversation_key": "T1:C1:1",
        "event_type": "message",
        "user_text": text,
        "reaction": None,
        "react_step": 0,
        "react_max_steps": 3,
        "react_done": False,
        "react_notes": [],
        "reasoning_note": "",
        "selected_action": "",
        "selected_skill": "",
        "action_input": {},
        "skill_input": {},
        "action_output": {},
        "skill_output": {},
        "execution_trace": [],
        "reply_text": "",
    }


def test_react_graph_continues_when_reasoner_emits_second_tool_call() -> None:
    tools = ToolRegistry()
    tools.register(
        ToolManifest(name="first_tool", description="first"),
        lambda _state: {"message": "first observation"},
    )
    tools.register(
        ToolManifest(name="second_tool", description="second"),
        lambda _state: {"message": "second observation"},
    )
    reasoner = _SequentialReasoner(
        rounds=[
            {
                "tool_calls": [
                    ModelToolCall(name="first_tool", arguments={}),
                ]
            },
            {
                "tool_calls": [
                    ModelToolCall(name="second_tool", arguments={}),
                ]
            },
            {
                "text": "final answer",
                "tool_calls": [],
            },
        ]
    )

    graph = build_graph(SkillRegistry(), tool_registry=tools, reasoner=reasoner)
    result = graph.invoke(_state("do two things"))

    assert result["reply_text"] == "final answer"
    assert result["react_done"] is True
    assert [step["action"] for step in result["execution_trace"]] == [
        "first_tool",
        "second_tool",
    ]
    assert reasoner.seen_payloads[1]["last_observation"]["message"] == "first observation"
    assert reasoner.seen_payloads[2]["last_observation"]["message"] == "second observation"


def test_observe_does_not_finish_after_single_tool_result() -> None:
    output = observe_node(
        {
            **_state(),
            "selected_action": "first_tool",
            "action_output": {"message": "first observation"},
        }
    )

    assert output["react_step"] == 1
    assert output["react_done"] is False
    assert output["execution_trace"][0]["observation"] == "first observation"

