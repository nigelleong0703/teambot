from teambot.agent.runtime import TeamBotRuntime


def test_runtime_bootstraps_with_minimal_profile(monkeypatch) -> None:
    monkeypatch.setenv("TOOLS_PROFILE", "minimal")
    agent = TeamBotRuntime(provider_manager=None)
    names = {manifest.name for manifest in agent.tool_registry.list_manifests()}
    assert names == {"activate_skill"}
    assert agent.graph is not None
    assert agent.plugin_host is not None
    assert not hasattr(agent, "registry")


def test_runtime_reload_reflects_profile_change(monkeypatch) -> None:
    monkeypatch.setenv("TOOLS_PROFILE", "minimal")
    agent = TeamBotRuntime(provider_manager=None)
    names_before = {manifest.name for manifest in agent.tool_registry.list_manifests()}
    assert names_before == {"activate_skill"}

    monkeypatch.setenv("TOOLS_PROFILE", "external_operation")
    agent.reload_runtime()
    names_after = {manifest.name for manifest in agent.tool_registry.list_manifests()}
    assert {
        "read_file",
        "write_file",
        "edit_file",
        "execute_shell_command",
        "browser_use",
        "get_current_time",
    } <= names_after
