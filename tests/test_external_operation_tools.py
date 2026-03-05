from __future__ import annotations

from pathlib import Path

from teambot.agents.core.graph import build_graph
from teambot.agents.core.policy import ExecutionPolicyGate
from teambot.agents.skills.registry import SkillManifest, SkillRegistry
from teambot.agents.tools import build_tool_registry
from teambot.domain.models import AgentState


def _state(next_skill: str, *, skill_input: dict[str, object] | None = None) -> AgentState:
    return {
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
        "skill_input": skill_input or {},
        "skill_output": {"next_skill": next_skill},
        "execution_trace": [],
        "reply_text": "",
    }


def _manifest_names() -> set[str]:
    registry = build_tool_registry(provider_manager=None)
    return {manifest.name for manifest in registry.list_manifests()}


def test_default_tool_registry_keeps_message_reply_only() -> None:
    names = _manifest_names()
    assert names == {"message_reply"}


def test_external_operation_tools_registration_and_risk_levels(
    monkeypatch,
) -> None:
    monkeypatch.setenv("TOOLS_PROFILE", "external_operation")
    registry = build_tool_registry(provider_manager=None)
    manifests = {manifest.name: manifest for manifest in registry.list_manifests()}

    expected = {
        "message_reply",
        "read_file",
        "write_file",
        "edit_file",
        "execute_shell_command",
        "browser_use",
        "get_current_time",
    }
    assert expected.issubset(set(manifests.keys()))
    assert manifests["write_file"].risk_level == "high"
    assert manifests["edit_file"].risk_level == "high"
    assert manifests["execute_shell_command"].risk_level == "high"


def test_optional_parity_tools_are_feature_flagged(monkeypatch) -> None:
    monkeypatch.setenv("TOOLS_PROFILE", "full")
    names = _manifest_names()
    assert "desktop_screenshot" in names
    assert "send_file_to_user" in names


def test_external_operation_tool_outputs_are_normalized_for_success_and_error(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("TOOLS_PROFILE", "external_operation")
    registry = build_tool_registry(provider_manager=None)
    file_path = tmp_path / "notes.txt"

    write_result = registry.invoke(
        "write_file",
        _state(
            "write_file",
            skill_input={"file_path": str(file_path), "content": "alpha\nbeta"},
        ),
    )
    assert isinstance(write_result, dict)
    assert "message" in write_result
    assert write_result.get("error") is not True

    read_result = registry.invoke(
        "read_file",
        _state(
            "read_file",
            skill_input={"file_path": str(file_path), "start_line": 1, "end_line": 1},
        ),
    )
    assert isinstance(read_result, dict)
    assert "message" in read_result
    assert "1: alpha" in str(read_result["message"])

    error_result = registry.invoke(
        "edit_file",
        _state(
            "edit_file",
            skill_input={"file_path": str(file_path), "old_text": "missing", "new_text": "x"},
        ),
    )
    assert isinstance(error_result, dict)
    assert error_result.get("error") is True
    assert "message" in error_result


def test_high_risk_external_operation_tool_is_blocked_by_policy_gate(monkeypatch) -> None:
    monkeypatch.setenv("TOOLS_PROFILE", "external_operation")
    skills = SkillRegistry()
    skills.register(SkillManifest(name="message_reply", description=""), lambda _s: {"message": "ok"})
    tools = build_tool_registry(provider_manager=None)

    graph = build_graph(
        skills,
        tool_registry=tools,
        policy_gate=ExecutionPolicyGate(allow_high_risk=False),
    )
    result = graph.invoke(
        _state(
            "execute_shell_command",
            skill_input={"command": "echo should-not-run"},
        )
    )

    assert result["selected_skill"] == "execute_shell_command"
    assert "High-risk action blocked by policy" in result["reply_text"]
    assert result["execution_trace"][0]["blocked"] is True


def test_runtime_falls_back_when_follow_up_action_is_unavailable() -> None:
    skills = SkillRegistry()
    skills.register(SkillManifest(name="message_reply", description=""), lambda _s: {"message": "fallback"})

    graph = build_graph(skills)
    result = graph.invoke(_state("tool_that_is_not_registered"))

    assert result["selected_skill"] == "message_reply"
    assert result["reply_text"] == "fallback"

