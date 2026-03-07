from __future__ import annotations

from teambot.app.slash_commands import (
    dispatch_slash_command,
    format_help_lines,
)


def test_help_lines_do_not_expose_tools_command() -> None:
    lines = format_help_lines(supports_debug=True)

    assert not any("/tools" in line for line in lines)


def test_dispatch_does_not_handle_removed_tools_command() -> None:
    action = dispatch_slash_command(
        "/tools",
        supports_debug=True,
        reload_runtime=lambda: None,
    )

    assert action.handled is False


def test_dispatch_handles_skills_command() -> None:
    action = dispatch_slash_command(
        "/skills",
        supports_debug=True,
        reload_runtime=lambda: None,
    )

    assert action.handled is True
