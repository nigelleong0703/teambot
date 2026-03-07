from teambot.mcp.bridge import register_mcp_tools
from teambot.mcp.config import load_mcp_runtime_config
from teambot.mcp.manager import MCPClientManager
from teambot.actions.tools.registry import ToolRegistry


def test_mcp_config_disabled_by_default() -> None:
    cfg = load_mcp_runtime_config()
    assert cfg.enabled is False
    assert cfg.servers == []


def test_mcp_manager_lists_tools_from_json(monkeypatch) -> None:
    monkeypatch.setenv("MCP_ENABLED", "true")
    monkeypatch.setenv(
        "MCP_SERVERS_JSON",
        '[{"name":"demo","tools":[{"name":"mcp_search","description":"Search MCP"}]}]',
    )
    cfg = load_mcp_runtime_config()
    manager = MCPClientManager()
    manager.init_from_config(cfg)
    names = {tool.name for tool in manager.list_tools()}
    assert names == {"mcp_search"}


def test_mcp_bridge_registers_tools_with_namesake_rename(monkeypatch) -> None:
    monkeypatch.setenv("MCP_ENABLED", "true")
    monkeypatch.setenv(
        "MCP_SERVERS_JSON",
        '[{"name":"demo","tools":[{"name":"read_file","description":"MCP read"}]}]',
    )
    cfg = load_mcp_runtime_config()
    manager = MCPClientManager()
    manager.init_from_config(cfg)

    registry = ToolRegistry()
    # Existing builtin-like tool
    from teambot.actions.tools.registry import ToolManifest

    registry.register(
        ToolManifest(name="read_file", description="builtin read", risk_level="low"),
        lambda _state: {"message": "builtin"},
    )
    register_mcp_tools(
        registry=registry,
        tools=manager.list_tools(),
        namesake_strategy="rename",
    )
    names = {manifest.name for manifest in registry.list_manifests()}
    assert "read_file" in names
    assert any(name.startswith("read_file__mcp_") for name in names)

