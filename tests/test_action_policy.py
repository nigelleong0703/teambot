from __future__ import annotations

from teambot.contracts.contracts import ModelToolCall, ModelToolInvocationResult
from teambot.agent.graph import build_graph
from teambot.agent.policy import ExecutionPolicyGate
from teambot.skills.registry import SkillManifest, SkillRegistry
from teambot.actions.tools.registry import ToolManifest, ToolRegistry
from teambot.domain.models import AgentState


def _state() -> AgentState:
    return {
        "conversation_key": "T1:C1:1",
        "recent_turns": [],
        "conversation_summary": "",
        "memory_system_prompt_suffix": "",
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
        "skill_output": {},
        "execution_trace": [],
        "reply_text": "",
    }


class _Planner:
    def __init__(self, action_name: str) -> None:
        self.action_name = action_name

    def has_role(self, role: str) -> bool:
        return role == "agent_model"

    def invoke_role_tools(self, *, role: str, system_prompt: str, payload: dict, tools: list):
        return ModelToolInvocationResult(
            text="",
            tool_calls=[ModelToolCall(name=self.action_name, arguments={})],
            provider="stub",
            model="stub",
        )

    def invoke_role_text(self, *, role: str, system_prompt: str, user_message: str):
        raise AssertionError("unexpected text-only path")


def test_tool_action_uses_unified_contract() -> None:
    skills = SkillRegistry()
    tools = ToolRegistry()

    skills.register(SkillManifest(name="create_task", description=""), lambda _s: {"message": "ok"})
    tools.register(
        ToolManifest(name="tool_echo", description="echo", risk_level="low"),
        lambda state: {"message": f"echo:{state['user_text']}"},
    )

    graph = build_graph(
        skills,
        tool_registry=tools,
        planner=_Planner("tool_echo"),
    )
    result = graph.invoke(_state())

    assert result["selected_skill"] == "tool_echo"
    assert result["reply_text"] == "echo:run tool"
    assert result["execution_trace"][0]["action"] == "tool_echo"
    assert result["execution_trace"][0]["blocked"] is False


def test_high_risk_action_is_blocked_by_policy_gate() -> None:
    skills = SkillRegistry()
    tools = ToolRegistry()

    skills.register(SkillManifest(name="create_task", description=""), lambda _s: {"message": "ok"})
    tools.register(
        ToolManifest(name="exec_command", description="danger", risk_level="high"),
        lambda _state: {"message": "should not execute"},
    )

    graph = build_graph(
        skills,
        tool_registry=tools,
        planner=_Planner("exec_command"),
        policy_gate=ExecutionPolicyGate(allow_high_risk=False),
    )
    result = graph.invoke(_state())

    assert result["selected_skill"] == "exec_command"
    assert "High-risk action blocked by policy" in result["reply_text"]
    assert result["execution_trace"][0]["blocked"] is True


def test_execution_policy_gate_can_load_from_runtime_config_file(
    monkeypatch,
    tmp_path,
) -> None:
    runtime_config = tmp_path / "config.json"
    runtime_config.write_text(
        '{"policy":{"allow_high_risk_actions":false,"high_risk_allowed_actions":["exec_command"]}}',
        encoding="utf-8",
    )
    monkeypatch.setenv("RUNTIME_CONFIG_FILE", str(runtime_config))

    policy = ExecutionPolicyGate.from_env()

    assert policy.check("exec_command", "high").allowed is True
    denied = policy.check("dangerous_tool", "high")
    assert denied.allowed is False
