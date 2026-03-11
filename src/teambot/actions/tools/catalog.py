from __future__ import annotations

from typing import Any

from ...contracts.contracts import ModelRoleInvoker
from ...domain.models import AgentState
from .external_operation_tools import (
    activate_skill,
    browser,
    desktop_screenshot,
    edit_file,
    execute_shell_command,
    get_current_time,
    read_file,
    send_file_to_user,
    web_fetch,
    write_file,
)
from .registry import ToolHandler, ToolManifest


def echo_tool(state: AgentState) -> dict[str, str]:
    return {"message": f"tool_echo:{state.get('user_text', '')}"}


def _schema(
    *,
    properties: dict[str, Any],
    required: list[str] | None = None,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "type": "object",
        "properties": properties,
    }
    if required:
        data["required"] = required
    return data


def builtin_tool_definitions(
    provider_manager: ModelRoleInvoker | None,
) -> dict[str, tuple[ToolManifest, ToolHandler]]:
    # provider_manager reserved for future provider-native tool integrations.
    _ = provider_manager
    return {
        "activate_skill": (
            ToolManifest(
                name="activate_skill",
                description="Load a skill document into the active reasoner context by skill name.",
                input_schema=_schema(
                    properties={
                        "skill_name": {
                            "type": "string",
                            "description": "Exact skill name from the available skill catalog.",
                        }
                    },
                    required=["skill_name"],
                ),
                risk_level="low",
            ),
            activate_skill,
        ),
        "read_file": (
            ToolManifest(
                name="read_file",
                description="Read UTF-8 text file content from working directory or absolute path.",
                input_schema=_schema(
                    properties={
                        "file_path": {"type": "string", "description": "Path to file."},
                        "start_line": {"type": "integer", "description": "Optional start line (1-based)."},
                        "end_line": {"type": "integer", "description": "Optional end line (1-based)."},
                    },
                    required=["file_path"],
                ),
                risk_level="low",
            ),
            read_file,
        ),
        "write_file": (
            ToolManifest(
                name="write_file",
                description="Create or overwrite UTF-8 text files.",
                input_schema=_schema(
                    properties={
                        "file_path": {"type": "string", "description": "Path to file."},
                        "content": {"type": "string", "description": "Full file content to write."},
                    },
                    required=["file_path", "content"],
                ),
                risk_level="high",
            ),
            write_file,
        ),
        "edit_file": (
            ToolManifest(
                name="edit_file",
                description="Find-and-replace text inside files.",
                input_schema=_schema(
                    properties={
                        "file_path": {"type": "string", "description": "Path to file."},
                        "old_text": {"type": "string", "description": "Text to find."},
                        "new_text": {"type": "string", "description": "Replacement text."},
                    },
                    required=["file_path", "old_text", "new_text"],
                ),
                risk_level="high",
            ),
            edit_file,
        ),
        "execute_shell_command": (
            ToolManifest(
                name="execute_shell_command",
                description="Execute a shell command in working directory.",
                input_schema=_schema(
                    properties={
                        "command": {"type": "string", "description": "Command to execute."},
                        "timeout_seconds": {"type": "integer", "description": "Optional timeout in seconds."},
                    },
                    required=["command"],
                ),
                risk_level="high",
            ),
            execute_shell_command,
        ),
        "web_fetch": (
            ToolManifest(
                name="web_fetch",
                description=(
                    "Fetch content from a specific URL for reading or extraction. "
                    "Prefer this when the user provides a URL and no page interaction is required."
                ),
                input_schema=_schema(
                    properties={
                        "url": {"type": "string", "description": "HTTP(S) URL."},
                        "timeout_seconds": {"type": "integer", "description": "Optional timeout in seconds."},
                        "max_chars": {
                            "type": "integer",
                            "description": "Optional maximum response characters to keep.",
                        },
                    },
                    required=["url"],
                ),
                risk_level="low",
            ),
            web_fetch,
        ),
        "browser": (
            ToolManifest(
                name="browser",
                description=(
                    "Control a real browser for interactive page workflows. "
                    "Use this only when page interaction, rendered-page inspection, screenshots, "
                    "or browser session state is required. Prefer web_fetch for simple URL content retrieval."
                ),
                input_schema=_schema(
                    properties={
                        "action": {
                            "type": "string",
                            "enum": ["open", "tabs", "snapshot", "act", "screenshot", "close"],
                            "description": "Browser action to perform.",
                        },
                        "url": {
                            "type": "string",
                            "description": "Optional URL for open-like actions.",
                        },
                        "target_id": {
                            "type": "string",
                            "description": "Optional target/tab identifier for follow-up browser actions.",
                        },
                        "request": {
                            "type": "object",
                            "description": "Optional nested action request payload for act-style browser calls.",
                        },
                    },
                    required=["action"],
                ),
                risk_level="low",
            ),
            browser,
        ),
        "get_current_time": (
            ToolManifest(
                name="get_current_time",
                description="Get current time for a timezone or local system timezone.",
                input_schema=_schema(
                    properties={
                        "timezone": {
                            "type": "string",
                            "description": "IANA timezone, e.g. Asia/Kuala_Lumpur. Optional.",
                        }
                    }
                ),
                risk_level="low",
            ),
            get_current_time,
        ),
        "desktop_screenshot": (
            ToolManifest(
                name="desktop_screenshot",
                description="Capture desktop screenshot (feature-gated placeholder).",
                input_schema=_schema(properties={}),
                risk_level="low",
            ),
            desktop_screenshot,
        ),
        "send_file_to_user": (
            ToolManifest(
                name="send_file_to_user",
                description="Prepare local file metadata for user delivery channel.",
                input_schema=_schema(
                    properties={
                        "file_path": {"type": "string", "description": "Path to file."},
                    },
                    required=["file_path"],
                ),
                risk_level="low",
            ),
            send_file_to_user,
        ),
        "tool_echo": (
            ToolManifest(
                name="tool_echo",
                description="Echo tool output for debugging action routing.",
                input_schema=_schema(
                    properties={
                        "text": {"type": "string", "description": "Optional text for debug echo."},
                    }
                ),
                risk_level="low",
            ),
            echo_tool,
        ),
        "exec_command": (
            ToolManifest(
                name="exec_command",
                description="Backward-compatible alias to execute_shell_command.",
                input_schema=_schema(
                    properties={
                        "command": {"type": "string", "description": "Command to execute."},
                        "timeout_seconds": {"type": "integer", "description": "Optional timeout in seconds."},
                    },
                    required=["command"],
                ),
                risk_level="high",
            ),
            execute_shell_command,
        ),
    }
