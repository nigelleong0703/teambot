from __future__ import annotations

from teambot.contracts.contracts import ModelToolCall, ModelToolInvocationResult
from teambot.agent.graph import build_graph
from teambot.skills.registry import SkillManifest, SkillRegistry
from teambot.actions.tools.registry import ToolManifest, ToolRegistry
from teambot.domain.models import AgentState


def _state(user_text: str) -> AgentState:
    return {
        "conversation_key": "T1:C1:1",
        "event_type": "message",
        "user_text": user_text,
        "reaction": None,
        "react_step": 0,
        "react_max_steps": 3,
        "react_done": False,
        "react_notes": [],
        "reasoning_note": "",
        "selected_skill": "",
        "skill_input": {},
        "skill_output": {},
        "reply_text": "",
    }


def test_max_step_guard_short_circuits_act_execution() -> None:
    registry = SkillRegistry()

    def should_not_run(_state: AgentState) -> dict[str, str]:
        raise AssertionError("act should be skipped when step guard is reached")

    registry.register(SkillManifest(name="create_task", description=""), should_not_run)
    registry.register(SkillManifest(name="handle_reaction", description=""), should_not_run)

    graph = build_graph(registry)
    state = _state("hello")
    state["react_step"] = 3
    state["react_max_steps"] = 3
    result = graph.invoke(state)

    assert result["reply_text"] == "Processed."
    assert result["react_done"] is True
    assert result["react_step"] == 3


def test_tool_result_is_followed_by_next_reasoner_turn() -> None:
    registry = SkillRegistry()
    tools = ToolRegistry()

    def lookup_time(_state: AgentState) -> dict[str, str]:
        return {"message": "task"}

    registry.register(SkillManifest(name="create_task", description=""), lookup_time)
    registry.register(SkillManifest(name="handle_reaction", description=""), lookup_time)
    tools.register(ToolManifest(name="get_current_time", description="time tool"), lookup_time)

    class _Planner:
        def __init__(self) -> None:
            self.calls = 0

        def has_role(self, role: str) -> bool:
            return role == "agent_model"

        def invoke_role_tools(self, *, role: str, system_prompt: str, payload: dict, tools: list):
            self.calls += 1
            if self.calls == 1:
                return ModelToolInvocationResult(
                    text="",
                    tool_calls=[ModelToolCall(name="get_current_time", arguments={})],
                    provider="stub",
                    model="stub",
                )
            return ModelToolInvocationResult(
                text="final after task",
                tool_calls=[],
                provider="stub",
                model="stub",
            )

        def invoke_role_text(self, *, role: str, system_prompt: str, user_message: str):
            raise AssertionError("unexpected text-only path")

    graph = build_graph(registry, tool_registry=tools, planner=_Planner())
    result = graph.invoke(_state("hello"))

    assert result["react_done"] is True
    assert result["reply_text"] == "final after task"
    assert result["execution_trace"][0]["action"] == "get_current_time"

