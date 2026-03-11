from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _has_python_sources(path: Path) -> bool:
    if not path.exists():
        return False
    return any(item.is_file() and item.suffix == ".py" for item in path.rglob("*.py"))


def test_agent_structure_matches_canonical_top_level_layout() -> None:
    agent_dir = ROOT / "src" / "teambot" / "agent"
    assert (agent_dir / "graph.py").exists()
    assert (agent_dir / "reason.py").exists()
    assert (agent_dir / "execution.py").exists()
    assert (agent_dir / "state.py").exists()
    assert (agent_dir / "policy.py").exists()
    assert (agent_dir / "runtime.py").exists()
    assert (agent_dir / "service.py").exists()
    assert (agent_dir / "orchestrator.py").exists()
    assert (agent_dir / "prompts" / "system_prompt.py").exists()

    providers_dir = ROOT / "src" / "teambot" / "providers"
    assert (providers_dir / "manager.py").exists()
    assert (providers_dir / "config.py").exists()
    assert (providers_dir / "registry.py").exists()

    skills_dir = ROOT / "src" / "teambot" / "skills"
    assert (skills_dir / "manager.py").exists()
    assert (skills_dir / "context.py").exists()
    assert not (skills_dir / "registry.py").exists()
    assert not (skills_dir / "runtime_loader.py").exists()
    assert not (skills_dir / "dynamic.py").exists()

    mcp_dir = ROOT / "src" / "teambot" / "mcp"
    assert (mcp_dir / "manager.py").exists()
    assert (mcp_dir / "bridge.py").exists()
    assert (mcp_dir / "config.py").exists()

    contracts_dir = ROOT / "src" / "teambot" / "contracts"
    assert (contracts_dir / "contracts.py").exists()

    tools_dir = ROOT / "src" / "teambot" / "actions" / "tools"
    assert (tools_dir / "registry.py").exists()
    assert (tools_dir / "runtime_builder.py").exists()
    assert (tools_dir / "external_operation_tools.py").exists()

    event_handlers_dir = ROOT / "src" / "teambot" / "actions" / "event_handlers"
    assert (event_handlers_dir / "registry.py").exists()
    assert (event_handlers_dir / "builtin.py").exists()

    assert not (ROOT / "src" / "teambot" / "runtime").exists()
    assert _has_python_sources(ROOT / "src" / "teambot" / "agent_core") is False
    assert _has_python_sources(ROOT / "src" / "teambot" / "interfaces") is False
    assert _has_python_sources(ROOT / "src" / "teambot" / "plugins") is False
    assert _has_python_sources(ROOT / "src" / "teambot" / "agents") is False
