from __future__ import annotations

import json
from typing import Any

from ..providers.manager import ROLE_AGENT
from ...agent_core.contracts import ModelRoleInvoker
from ...domain.models import AgentState
from ..prompts import build_system_prompt_from_working_dir
from .external_operation_tools import (
    browser_use,
    desktop_screenshot,
    edit_file,
    execute_shell_command,
    get_current_time,
    read_file,
    send_file_to_user,
    write_file,
)
from .registry import ToolHandler, ToolManifest


def _deterministic_message_reply(state: AgentState) -> dict[str, str]:
    text = state.get("user_text", "").strip()
    return {
        "message": (
            "Acknowledged. The MVP currently replies using deterministic thread routing."
            f"\n\nYou said: {text}"
        ),
    }


def _extract_message_text(raw_text: str) -> str:
    text = raw_text.strip()
    if not text:
        return ""
    if text.startswith("{") and text.endswith("}"):
        try:
            parsed = json.loads(text)
        except Exception:
            return text
        if isinstance(parsed, dict):
            msg = parsed.get("message")
            if isinstance(msg, str) and msg.strip():
                return msg.strip()
    return text


class MessageReplyTool:
    def __init__(self, provider_manager: ModelRoleInvoker | None) -> None:
        self._provider_manager = provider_manager

    def __call__(self, state: AgentState) -> dict[str, str]:
        manager = self._provider_manager
        if manager is None or not manager.has_role(ROLE_AGENT):
            return _deterministic_message_reply(state)

        try:
            result = manager.invoke_role_text(
                role=ROLE_AGENT,
                system_prompt=build_system_prompt_from_working_dir(),
                user_message=str(state.get("user_text", "")).strip(),
            )
        except Exception:
            return _deterministic_message_reply(state)

        message = _extract_message_text(result.text)
        if message:
            return {"message": message}
        return _deterministic_message_reply(state)


def echo_tool(state: AgentState) -> dict[str, str]:
    return {"message": f"tool_echo:{state.get('user_text', '')}"}


def builtin_tool_definitions(
    provider_manager: ModelRoleInvoker | None,
) -> dict[str, tuple[ToolManifest, ToolHandler]]:
    return {
        "message_reply": (
            ToolManifest(
                name="message_reply",
                description="Default conversational message tool.",
                risk_level="low",
            ),
            MessageReplyTool(provider_manager),
        ),
        "read_file": (
            ToolManifest(
                name="read_file",
                description="Read UTF-8 text file content from working directory or absolute path.",
                risk_level="low",
            ),
            read_file,
        ),
        "write_file": (
            ToolManifest(
                name="write_file",
                description="Create or overwrite UTF-8 text files.",
                risk_level="high",
            ),
            write_file,
        ),
        "edit_file": (
            ToolManifest(
                name="edit_file",
                description="Find-and-replace text inside files.",
                risk_level="high",
            ),
            edit_file,
        ),
        "execute_shell_command": (
            ToolManifest(
                name="execute_shell_command",
                description="Execute a shell command in working directory.",
                risk_level="high",
            ),
            execute_shell_command,
        ),
        "browser_use": (
            ToolManifest(
                name="browser_use",
                description="Fetch URL content over HTTP(S) and return a preview.",
                risk_level="low",
            ),
            browser_use,
        ),
        "get_current_time": (
            ToolManifest(
                name="get_current_time",
                description="Get current time for a timezone or local system timezone.",
                risk_level="low",
            ),
            get_current_time,
        ),
        "desktop_screenshot": (
            ToolManifest(
                name="desktop_screenshot",
                description="Capture desktop screenshot (feature-gated placeholder).",
                risk_level="low",
            ),
            desktop_screenshot,
        ),
        "send_file_to_user": (
            ToolManifest(
                name="send_file_to_user",
                description="Prepare local file metadata for user delivery channel.",
                risk_level="low",
            ),
            send_file_to_user,
        ),
        "tool_echo": (
            ToolManifest(
                name="tool_echo",
                description="Echo tool output for debugging action routing.",
                risk_level="low",
            ),
            echo_tool,
        ),
        "exec_command": (
            ToolManifest(
                name="exec_command",
                description="Backward-compatible alias to execute_shell_command.",
                risk_level="high",
            ),
            execute_shell_command,
        ),
    }

