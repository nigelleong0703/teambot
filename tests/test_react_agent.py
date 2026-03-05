from teambot.agents.react_agent import TeamBotReactAgent


def test_react_agent_bootstraps_runtime_with_minimal_profile(monkeypatch) -> None:
    monkeypatch.setenv("TOOLS_PROFILE", "minimal")
    agent = TeamBotReactAgent(provider_manager=None, dynamic_skills_dir=None)
    names = {manifest.name for manifest in agent.tool_registry.list_manifests()}
    assert names == set()
    assert agent.graph is not None
    assert agent.plugin_host is not None


def test_react_agent_reload_runtime_reflects_profile_change(monkeypatch) -> None:
    monkeypatch.setenv("TOOLS_PROFILE", "minimal")
    agent = TeamBotReactAgent(provider_manager=None, dynamic_skills_dir=None)
    names_before = {manifest.name for manifest in agent.tool_registry.list_manifests()}
    assert names_before == set()

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
