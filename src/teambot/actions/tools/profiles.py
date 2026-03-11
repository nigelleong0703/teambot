from __future__ import annotations

TOOL_PROFILE_MINIMAL = "minimal"
TOOL_PROFILE_EXTERNAL_OPERATION = "external_operation"
TOOL_PROFILE_FULL = "full"

PROFILE_DESCRIPTIONS: dict[str, str] = {
    TOOL_PROFILE_MINIMAL: "activate_skill only (model can still answer directly)",
    TOOL_PROFILE_EXTERNAL_OPERATION: (
        "activate_skill + read/write/edit file + execute shell + browser + current time"
    ),
    TOOL_PROFILE_FULL: (
        "activate_skill + external_operation + desktop_screenshot + send_file_to_user"
    ),
}

_PROFILE_TOOLS: dict[str, set[str]] = {
    TOOL_PROFILE_MINIMAL: set(),
    TOOL_PROFILE_EXTERNAL_OPERATION: {
        "read_file",
        "write_file",
        "edit_file",
        "execute_shell_command",
        "browser_use",
        "get_current_time",
    },
    TOOL_PROFILE_FULL: {
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


def describe_profiles() -> dict[str, str]:
    return dict(PROFILE_DESCRIPTIONS)
