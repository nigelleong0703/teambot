from teambot.agents.core.graph import build_graph
from teambot.agents.core.policy import ExecutionPolicyGate
from teambot.agents.skills.registry import SkillManifest, SkillRegistry
from teambot.agents.tools.registry import ToolManifest, ToolRegistry
from teambot.models import AgentState


def _state(next_skill: str) -> AgentState:
    return {
        "conversation_key": "T1:C1:1",
        "event_type": "message",
        "user_text": "run tool",
        "reaction": None,
        "react_step": 0,
        "react_max_steps": 3,
        "react_done": False,
        "react_notes": [],
        "reasoning_note": "",
        "selected_skill": "",
        "skill_input": {},
        "skill_output": {"next_skill": next_skill},
        "execution_trace": [],
        "reply_text": "",
    }


def test_tool_action_uses_unified_contract() -> None:
    skills = SkillRegistry()
    tools = ToolRegistry()

    skills.register(SkillManifest(name="general_reply", description=""), lambda _s: {"message": "ok"})
    tools.register(
        ToolManifest(name="tool_echo", description="echo", risk_level="low"),
        lambda state: {"message": f"echo:{state['user_text']}"},
    )

    graph = build_graph(
        skills,
        tool_registry=tools,
    )
    result = graph.invoke(_state("tool_echo"))

    assert result["selected_skill"] == "tool_echo"
    assert result["reply_text"] == "echo:run tool"
    assert result["execution_trace"][0]["action"] == "tool_echo"
    assert result["execution_trace"][0]["blocked"] is False


def test_high_risk_action_is_blocked_by_policy_gate() -> None:
    skills = SkillRegistry()
    tools = ToolRegistry()

    skills.register(SkillManifest(name="general_reply", description=""), lambda _s: {"message": "ok"})
    tools.register(
        ToolManifest(name="exec_command", description="danger", risk_level="high"),
        lambda _state: {"message": "should not execute"},
    )

    graph = build_graph(
        skills,
        tool_registry=tools,
        policy_gate=ExecutionPolicyGate(allow_high_risk=False),
    )
    result = graph.invoke(_state("exec_command"))

    assert result["selected_skill"] == "exec_command"
    assert "High-risk action blocked by policy" in result["reply_text"]
    assert result["execution_trace"][0]["blocked"] is True
