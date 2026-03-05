from teambot.agents.tools.namesake import (
    apply_namesake_strategy,
    rename_for_namesake,
)
from teambot.agents.tools.profiles import (
    TOOL_PROFILE_EXTERNAL_OPERATION,
    TOOL_PROFILE_FULL,
    TOOL_PROFILE_MINIMAL,
    resolve_tool_profile,
)


def test_resolve_tool_profile_minimal() -> None:
    assert resolve_tool_profile(TOOL_PROFILE_MINIMAL) == set()


def test_resolve_tool_profile_external_operation() -> None:
    names = resolve_tool_profile(TOOL_PROFILE_EXTERNAL_OPERATION)
    assert "read_file" in names
    assert "execute_shell_command" in names


def test_resolve_tool_profile_full_includes_optional_tools() -> None:
    names = resolve_tool_profile(TOOL_PROFILE_FULL)
    assert "desktop_screenshot" in names
    assert "send_file_to_user" in names


def test_namesake_skip_keeps_original_name() -> None:
    assert apply_namesake_strategy(
        existing={"read_file"},
        incoming_name="read_file",
        strategy="skip",
    ) is None


def test_namesake_override_keeps_same_name() -> None:
    assert apply_namesake_strategy(
        existing={"read_file"},
        incoming_name="read_file",
        strategy="override",
    ) == "read_file"


def test_namesake_raise_throws_on_conflict() -> None:
    try:
        apply_namesake_strategy(
            existing={"read_file"},
            incoming_name="read_file",
            strategy="raise",
        )
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert "namesake conflict" in str(exc)


def test_namesake_rename_appends_suffix() -> None:
    assert rename_for_namesake(
        existing={"read_file", "read_file__mcp_1"},
        incoming_name="read_file",
        namespace="mcp",
    ) == "read_file__mcp_2"
