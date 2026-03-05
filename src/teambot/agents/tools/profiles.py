from __future__ import annotations

TOOL_PROFILE_MINIMAL = "minimal"
TOOL_PROFILE_EXTERNAL_OPERATION = "external_operation"
TOOL_PROFILE_FULL = "full"

_PROFILE_TOOLS: dict[str, set[str]] = {
    TOOL_PROFILE_MINIMAL: {
        "message_reply",
    },
    TOOL_PROFILE_EXTERNAL_OPERATION: {
        "message_reply",
        "read_file",
        "write_file",
        "edit_file",
        "execute_shell_command",
        "browser_use",
        "get_current_time",
    },
    TOOL_PROFILE_FULL: {
        "message_reply",
        "read_file",
        "write_file",
        "edit_file",
        "execute_shell_command",
        "browser_use",
        "get_current_time",
        "desktop_screenshot",
        "send_file_to_user",
    },
}


def normalize_tool_profile(profile: str | None) -> str:
    raw = (profile or "").strip().lower()
    if raw in _PROFILE_TOOLS:
        return raw
    return TOOL_PROFILE_MINIMAL


def resolve_tool_profile(profile: str | None) -> set[str]:
    normalized = normalize_tool_profile(profile)
    return set(_PROFILE_TOOLS[normalized])
