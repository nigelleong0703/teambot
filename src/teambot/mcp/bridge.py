from __future__ import annotations

from .manager import MCPTool
from ..actions.tools.namesake import apply_namesake_strategy
from ..actions.tools.registry import ToolManifest, ToolRegistry


def register_mcp_tools(
    *,
    registry: ToolRegistry,
    tools: list[MCPTool],
    namesake_strategy: str = "skip",
) -> dict[str, str]:
    existing = {manifest.name for manifest in registry.list_manifests()}
    aliases: dict[str, str] = {}

    for tool in tools:
        resolved_name = apply_namesake_strategy(
            existing=existing,
            incoming_name=tool.name,
            strategy=namesake_strategy,
            namespace="mcp",
        )
        if resolved_name is None:
            continue
        manifest = ToolManifest(
            name=resolved_name,
            description=tool.description,
            risk_level=tool.risk_level or "low",
        )
        registry.register(manifest, tool.invoke)
        existing.add(resolved_name)
        aliases[tool.name] = resolved_name

    return aliases
