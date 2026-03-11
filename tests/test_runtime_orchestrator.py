from teambot.agent.orchestrator import RuntimeOrchestrator


def test_orchestrator_builds_runtime_components() -> None:
    orchestrator = RuntimeOrchestrator(provider_manager=None)
    bundle = orchestrator.build()
    assert bundle.tool_registry is not None
    assert bundle.mcp_manager is not None
    assert not hasattr(bundle, "plugin_host")
    assert not hasattr(bundle, "skill_registry")


def test_orchestrator_injects_mcp_tools(monkeypatch) -> None:
    monkeypatch.setenv("TOOLS_PROFILE", "minimal")
    monkeypatch.setenv("MCP_ENABLED", "true")
    monkeypatch.setenv(
        "MCP_SERVERS_JSON",
        '[{"name":"demo","tools":[{"name":"mcp_lookup","description":"Lookup"}]}]',
    )
    orchestrator = RuntimeOrchestrator(provider_manager=None)
    bundle = orchestrator.build()
    names = {manifest.name for manifest in bundle.tool_registry.list_manifests()}
    assert "mcp_lookup" in names
