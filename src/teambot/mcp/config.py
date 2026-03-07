from __future__ import annotations

import json
import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class MCPToolConfig:
    name: str
    description: str
    risk_level: str = "low"
    default_message: str = ""


@dataclass(frozen=True)
class MCPServerConfig:
    name: str
    tools: list[MCPToolConfig] = field(default_factory=list)


@dataclass(frozen=True)
class MCPRuntimeConfig:
    enabled: bool
    servers: list[MCPServerConfig] = field(default_factory=list)


def _env_true(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes"}


def load_mcp_runtime_config() -> MCPRuntimeConfig:
    enabled = _env_true("MCP_ENABLED")
    if not enabled:
        return MCPRuntimeConfig(enabled=False, servers=[])

    raw = os.getenv("MCP_SERVERS_JSON", "").strip()
    if not raw:
        return MCPRuntimeConfig(enabled=True, servers=[])

    try:
        parsed = json.loads(raw)
    except Exception:
        return MCPRuntimeConfig(enabled=True, servers=[])

    if not isinstance(parsed, list):
        return MCPRuntimeConfig(enabled=True, servers=[])

    servers: list[MCPServerConfig] = []
    for server_raw in parsed:
        if not isinstance(server_raw, dict):
            continue
        server_name = str(server_raw.get("name") or "").strip()
        if not server_name:
            continue

        tools_raw = server_raw.get("tools") or []
        tools: list[MCPToolConfig] = []
        if isinstance(tools_raw, list):
            for tool_raw in tools_raw:
                if not isinstance(tool_raw, dict):
                    continue
                tool_name = str(tool_raw.get("name") or "").strip()
                if not tool_name:
                    continue
                description = str(tool_raw.get("description") or f"MCP tool: {tool_name}")
                risk_level = str(tool_raw.get("risk_level") or "low")
                default_message = str(tool_raw.get("default_message") or "")
                tools.append(
                    MCPToolConfig(
                        name=tool_name,
                        description=description,
                        risk_level=risk_level,
                        default_message=default_message,
                    )
                )
        servers.append(MCPServerConfig(name=server_name, tools=tools))

    return MCPRuntimeConfig(enabled=True, servers=servers)
