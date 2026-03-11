from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from teambot.contracts.contracts import ModelTextInvocationResult, ModelToolCall, ModelToolInvocationResult
from teambot.agent.graph import build_graph
from teambot.actions.tools.registry import ToolManifest, ToolRegistry
from teambot.domain.models import AgentState


@dataclass
class _PlannerStub:
    tool_calls: list[ModelToolCall]
    text: str = ""

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
        return ModelToolInvocationResult(
            text=self.text,
            tool_calls=self.tool_calls,
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
        return ModelTextInvocationResult(
            text=self.text,
            provider="stub",
            model="stub-model",
        )

    def invoke_role_json(self, **_: Any):  # pragma: no cover - legacy compatibility
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
        "selected_skill": "",
        "skill_input": {},
        "skill_output": {},
        "execution_trace": [],
        "reply_text": "",
    }


def test_reason_uses_planner_action_decision() -> None:
    tools = ToolRegistry()
    tools.register(
        ToolManifest(name="get_current_time", description="time tool"),
        lambda _state: {"message": "time:ok"},
    )
    planner = _PlannerStub(
        tool_calls=[
            ModelToolCall(
                name="get_current_time",
                arguments={"timezone": "Asia/Kuala_Lumpur"},
            )
        ]
    )

    graph = build_graph(tool_registry=tools, planner=planner)
    result = graph.invoke(_state("check my current time"))

    assert result["selected_skill"] == "get_current_time"
    assert result["reply_text"] == "time:ok"


def test_reason_uses_planner_final_decision() -> None:
    planner = _PlannerStub(
        tool_calls=[],
        text="Hello from planner final",
    )
    graph = build_graph(planner=planner)
    result = graph.invoke(_state("hello"))

    assert result["react_done"] is True
    assert result["reply_text"] == "Hello from planner final"
