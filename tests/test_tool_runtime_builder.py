from teambot.agents.tools.runtime_builder import build_runtime_tool_registry


def test_minimal_profile_contains_message_reply_only() -> None:
    registry = build_runtime_tool_registry(profile="minimal", provider_manager=None)
    names = {manifest.name for manifest in registry.list_manifests()}
    assert names == {"message_reply"}


def test_external_operation_profile_contains_external_tools() -> None:
    registry = build_runtime_tool_registry(
        profile="external_operation",
        provider_manager=None,
    )
    names = {manifest.name for manifest in registry.list_manifests()}
    assert {
        "message_reply",
        "read_file",
        "write_file",
        "edit_file",
        "execute_shell_command",
        "browser_use",
        "get_current_time",
    }.issubset(names)


def test_full_profile_contains_optional_tools() -> None:
    registry = build_runtime_tool_registry(profile="full", provider_manager=None)
    names = {manifest.name for manifest in registry.list_manifests()}
    assert "desktop_screenshot" in names
    assert "send_file_to_user" in names
