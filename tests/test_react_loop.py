from teambot.agents.core.graph import build_graph
from teambot.agents.skills.registry import SkillManifest, SkillRegistry
from teambot.domain.models import AgentState


def test_react_graph_can_chain_follow_up_skill() -> None:
    registry = SkillRegistry()

    def second_skill(state: AgentState) -> dict[str, str]:
        payload = state.get("skill_input", {})
        return {"message": f"second step done ({payload.get('value')})"}

    registry.register(SkillManifest(name="second", description=""), second_skill)
    registry.register(SkillManifest(name="create_task", description=""), second_skill)
    registry.register(SkillManifest(name="handle_reaction", description=""), second_skill)

    graph = build_graph(registry)
    state: AgentState = {
        "conversation_key": "T1:C1:1",
        "event_type": "message",
        "user_text": "hello",
        "reaction": None,
        "react_step": 0,
        "react_max_steps": 3,
        "react_done": False,
        "react_notes": [],
        "reasoning_note": "",
        "selected_skill": "",
        "skill_input": {},
        "skill_output": {
            "next_skill": "second",
            "next_skill_input": {"value": "from-first"},
        },
        "reply_text": "",
    }

    result = graph.invoke(state)

    assert result["selected_skill"] == "second"
    assert result["reply_text"] == "second step done (from-first)"
    assert result["react_done"] is True
    assert result["react_step"] == 1
    assert len(result["react_notes"]) == 1
    assert len(result["execution_trace"]) == 1

