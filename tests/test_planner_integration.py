from teambot.agents.graph import build_graph
from teambot.agents.planner import PlanResult, PlannerError
from teambot.agents.skills.registry import SkillManifest, SkillRegistry
from teambot.models import AgentState


class _DonePlanner:
    def plan(self, state: AgentState, available_skills: list[SkillManifest]) -> PlanResult:
        return PlanResult(done=True, final_message="Model returned final answer directly")


class _FailPlanner:
    def plan(self, state: AgentState, available_skills: list[SkillManifest]) -> PlanResult:
        raise PlannerError("simulated model failure")


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


def test_done_plan_short_circuits_act_execution() -> None:
    registry = SkillRegistry()

    def should_not_run(_state: AgentState) -> dict[str, str]:
        raise AssertionError("act should be skipped when planner marks done=true")

    registry.register(SkillManifest(name="general_reply", description=""), should_not_run)
    registry.register(SkillManifest(name="create_task", description=""), should_not_run)
    registry.register(SkillManifest(name="handle_reaction", description=""), should_not_run)

    graph = build_graph(registry, planner=_DonePlanner())
    result = graph.invoke(_state("hello"))

    assert result["reply_text"] == "Model returned final answer directly"
    assert result["react_done"] is True
    assert result["react_step"] == 0


def test_planner_failure_falls_back_to_rule_planner() -> None:
    registry = SkillRegistry()

    def general_reply(state: AgentState) -> dict[str, str]:
        return {"message": f"fallback:{state['user_text']}"}

    def create_task(_state: AgentState) -> dict[str, str]:
        return {"message": "Task recorded: by fallback"}

    registry.register(SkillManifest(name="general_reply", description=""), general_reply)
    registry.register(SkillManifest(name="create_task", description=""), create_task)
    registry.register(SkillManifest(name="handle_reaction", description=""), general_reply)

    graph = build_graph(registry, planner=_FailPlanner())
    result = graph.invoke(_state("/todo write report"))

    assert result["selected_skill"] == "create_task"
    assert "Task recorded" in result["reply_text"]
    assert "fallback to rule planner" in result["reasoning_note"]
