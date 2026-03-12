from __future__ import annotations

from pathlib import Path
from urllib.error import URLError

from teambot.contracts.contracts import ModelToolCall, ModelToolInvocationResult
from teambot.agent.graph import build_graph
from teambot.agent.policy import ExecutionPolicyGate
from teambot.actions.tools import build_tool_registry
from teambot.domain.models import AgentState


def _state(*, user_text: str = "hello") -> AgentState:
    return {
        "conversation_key": "T1:C1:1",
        "recent_turns": [],
        "conversation_summary": "",
        "memory_system_prompt_suffix": "",
        "event_type": "message",
        "user_text": user_text,
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


class _Planner:
    def __init__(self, action_name: str, arguments: dict[str, object] | None = None) -> None:
        self.action_name = action_name
        self.arguments = arguments or {}

    def has_role(self, role: str) -> bool:
        return role == "agent_model"

    def invoke_role_tools(self, *, role: str, system_prompt: str, payload: dict, tools: list):
        return ModelToolInvocationResult(
            text="",
            tool_calls=[ModelToolCall(name=self.action_name, arguments=self.arguments)],
            provider="stub",
            model="stub",
        )

    def invoke_role_text(self, *, role: str, system_prompt: str, user_message: str):
        raise AssertionError("unexpected text-only path")


def _manifest_names() -> set[str]:
    registry = build_tool_registry(provider_manager=None)
    return {manifest.name for manifest in registry.list_manifests()}


def test_default_tool_registry_keeps_minimal_empty() -> None:
    names = _manifest_names()
    assert names == {"activate_skill"}


def test_activate_skill_tool_is_always_available_and_low_risk() -> None:
    registry = build_tool_registry(provider_manager=None)
    manifests = {manifest.name: manifest for manifest in registry.list_manifests()}

    assert "activate_skill" in manifests
    assert manifests["activate_skill"].risk_level == "low"


def test_external_operation_tools_registration_and_risk_levels(
    monkeypatch,
) -> None:
    monkeypatch.setenv("TOOLS_PROFILE", "external_operation")
    registry = build_tool_registry(provider_manager=None)
    manifests = {manifest.name: manifest for manifest in registry.list_manifests()}

    expected = {
        "read_file",
        "write_file",
        "edit_file",
        "execute_shell_command",
        "web_fetch",
        "browser",
        "get_current_time",
        "todo_read",
        "todo_write",
    }
    assert expected.issubset(set(manifests.keys()))
    assert "browser_use" not in manifests
    assert manifests["write_file"].risk_level == "high"
    assert manifests["edit_file"].risk_level == "high"
    assert manifests["execute_shell_command"].risk_level == "high"
    assert manifests["todo_read"].risk_level == "low"
    assert manifests["todo_write"].risk_level == "low"


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
        {**_state(), "action_input": {"file_path": str(file_path), "content": "alpha\nbeta"}},
    )
    assert isinstance(write_result, dict)
    assert "message" in write_result
    assert write_result.get("error") is not True

    read_result = registry.invoke(
        "read_file",
        {
            **_state(),
            "action_input": {"file_path": str(file_path), "start_line": 1, "end_line": 1},
        },
    )
    assert isinstance(read_result, dict)
    assert "message" in read_result
    assert "1: alpha" in str(read_result["message"])

    error_result = registry.invoke(
        "edit_file",
        {
            **_state(),
            "action_input": {"file_path": str(file_path), "old_text": "missing", "new_text": "x"},
        },
    )
    assert isinstance(error_result, dict)
    assert error_result.get("error") is True
    assert "message" in error_result


def test_todo_tools_round_trip_document_backed_todo_markdown(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("TOOLS_PROFILE", "external_operation")
    registry = build_tool_registry(provider_manager=None)
    state = {**_state(), "runtime_working_dir": str(tmp_path)}

    write_result = registry.invoke(
        "todo_write",
        {
            **state,
            "action_input": {
                "todos": [
                    {
                        "content": "Design document-backed todo storage",
                        "active_form": "Designing document-backed todo storage",
                        "status": "in_progress",
                    },
                    {
                        "content": "Add todo repository",
                        "active_form": "Adding todo repository",
                        "status": "pending",
                    },
                ]
            },
        },
    )

    assert write_result.get("error") is not True
    assert (tmp_path / "todo.md").exists()
    assert "## 1. Design document-backed todo storage" in (tmp_path / "todo.md").read_text(encoding="utf-8")

    read_result = registry.invoke("todo_read", state)

    assert read_result.get("error") is not True
    assert read_result.get("todos") == [
        {
            "content": "Design document-backed todo storage",
            "active_form": "Designing document-backed todo storage",
            "status": "in_progress",
        },
        {
            "content": "Add todo repository",
            "active_form": "Adding todo repository",
            "status": "pending",
        },
    ]


def test_todo_write_returns_error_for_invalid_progress_shape(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("TOOLS_PROFILE", "external_operation")
    registry = build_tool_registry(provider_manager=None)

    result = registry.invoke(
        "todo_write",
        {
            **_state(),
            "runtime_working_dir": str(tmp_path),
            "action_input": {
                "todos": [
                    {
                        "content": "Design document-backed todo storage",
                        "active_form": "Designing document-backed todo storage",
                        "status": "pending",
                    }
                ]
            },
        },
    )

    assert result.get("error") is True
    assert "exactly one in_progress" in str(result.get("message", ""))


def test_web_fetch_requires_explicit_url(monkeypatch) -> None:
    monkeypatch.setenv("TOOLS_PROFILE", "external_operation")
    registry = build_tool_registry(provider_manager=None)
    result = registry.invoke(
        "web_fetch",
        _state(user_text="check this page https://www.google.com"),
    )

    assert result.get("error") is True
    assert "`url` is required" in str(result.get("message", "")).lower()


def test_web_fetch_returns_metadata_and_truncated_content(monkeypatch) -> None:
    monkeypatch.setenv("TOOLS_PROFILE", "external_operation")
    registry = build_tool_registry(provider_manager=None)
    from teambot.actions.tools import external_operation_tools as eot

    class _Response:
        status = 200

        def __init__(self) -> None:
            self.headers = {"Content-Type": "text/html; charset=utf-8"}

        def read(self, _max_bytes: int) -> bytes:
            return b"hello world body"

        def geturl(self) -> str:
            return "https://example.com/final"

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    monkeypatch.setattr(eot, "urlopen", lambda *args, **kwargs: _Response())

    result = registry.invoke(
        "web_fetch",
        {
            **_state(),
            "action_input": {"url": "https://example.com", "max_chars": 5},
        },
    )

    assert result.get("error") is not True
    assert result.get("status_code") == 200
    assert result.get("content_type") == "text/html; charset=utf-8"
    assert result.get("final_url") == "https://example.com/final"
    assert result.get("content") == "hello"
    assert "Fetched https://example.com" in str(result.get("message", ""))


def test_browser_requires_action(monkeypatch) -> None:
    monkeypatch.setenv("TOOLS_PROFILE", "external_operation")
    registry = build_tool_registry(provider_manager=None)

    result = registry.invoke("browser", _state())

    assert result.get("error") is True
    assert "`action` is required" in str(result.get("message", "")).lower()


def test_browser_rejects_unsupported_action(monkeypatch) -> None:
    monkeypatch.setenv("TOOLS_PROFILE", "external_operation")
    registry = build_tool_registry(provider_manager=None)

    result = registry.invoke(
        "browser",
        {
            **_state(),
            "action_input": {"action": "start"},
        },
    )

    assert result.get("error") is True
    assert "unsupported browser action" in str(result.get("message", "")).lower()


def test_runtime_working_dir_overrides_agent_home_workdir_for_shell_and_file_tools(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TOOLS_PROFILE", "external_operation")
    monkeypatch.setenv("AGENT_HOME", "/home/nigelleong/.teambot/agents/tester")
    registry = build_tool_registry(provider_manager=None)

    state = {
        **_state(user_text="ls"),
        "runtime_working_dir": str(tmp_path),
    }

    shell_result = registry.invoke(
        "execute_shell_command",
        {
            **state,
            "action_input": {"command": "pwd"},
        },
    )
    assert shell_result.get("error") is not True
    assert tmp_path.name in str(shell_result.get("message", ""))

    file_result = registry.invoke(
        "write_file",
        {
            **state,
            "action_input": {"file_path": "notes.txt", "content": "hello"},
        },
    )
    assert file_result.get("error") is not True
    assert (tmp_path / "notes.txt").exists()


def test_agent_home_workdir_is_default_for_relative_file_and_shell_operations(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TOOLS_PROFILE", "external_operation")
    monkeypatch.setenv("AGENT_HOME", str(tmp_path / "agents" / "default"))
    registry = build_tool_registry(provider_manager=None)

    shell_result = registry.invoke(
        "execute_shell_command",
        {
            **_state(user_text="pwd"),
            "action_input": {"command": "pwd"},
        },
    )
    assert shell_result.get("error") is not True
    assert str((tmp_path / "agents" / "default" / "work").resolve()) in str(
        shell_result.get("message", "")
    )

    file_result = registry.invoke(
        "write_file",
        {
            **_state(),
            "action_input": {"file_path": "notes.txt", "content": "hello"},
        },
    )
    assert file_result.get("error") is not True
    assert (tmp_path / "agents" / "default" / "work" / "notes.txt").exists()


def test_high_risk_external_operation_tool_is_blocked_by_policy_gate(monkeypatch) -> None:
    monkeypatch.setenv("TOOLS_PROFILE", "external_operation")
    tools = build_tool_registry(provider_manager=None)

    graph = build_graph(
        tool_registry=tools,
        planner=_Planner("execute_shell_command", {"command": "echo should-not-run"}),
        policy_gate=ExecutionPolicyGate(allow_high_risk=False),
    )
    result = graph.invoke(_state())

    assert result["selected_action"] == "execute_shell_command"
    assert "High-risk action blocked by policy" in result["reply_text"]
    assert result["execution_trace"][0]["blocked"] is True


def test_unknown_model_tool_call_finishes_safely() -> None:
    monkey_tools = build_tool_registry(provider_manager=None)

    graph = build_graph(
        tool_registry=monkey_tools,
        planner=_Planner("tool_that_is_not_registered"),
    )
    result = graph.invoke(_state())

    assert result["react_done"] is True
    assert "could not map" in result["reply_text"].lower()
