from teambot.agents.core.graph import build_graph
from teambot.agents.skills.registry import SkillManifest, SkillRegistry
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


def test_unknown_follow_up_finishes_safely() -> None:
    registry = SkillRegistry()

    def create_task(_state: AgentState) -> dict[str, str]:
        return {"message": "task"}

    registry.register(SkillManifest(name="create_task", description=""), create_task)
    registry.register(SkillManifest(name="handle_reaction", description=""), create_task)

    graph = build_graph(registry)
    state = _state("hello")
    state["skill_output"] = {"next_skill": "missing_action"}
    result = graph.invoke(state)

    assert result["react_done"] is True
    assert "could not continue" in result["reply_text"].lower()

