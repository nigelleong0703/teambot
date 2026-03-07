from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from ..domain.models import AgentState
from .config import MCPRuntimeConfig, MCPToolConfig


MCPHandler = Callable[[AgentState], dict[str, Any]]


def _get_action_input(state: AgentState) -> dict[str, Any]:
    payload = state.get("action_input")
    if not isinstance(payload, dict):
        payload = state.get("skill_input")
    if isinstance(payload, dict):
        return payload
    return {}


@dataclass(frozen=True)
class MCPTool:
    name: str
    description: str
    risk_level: str
    handler: MCPHandler
    server_name: str

    def invoke(self, state: AgentState) -> dict[str, Any]:
        return self.handler(state)


class MCPClientManager:
    def __init__(self) -> None:
        self._tools: list[MCPTool] = []
        self._config: MCPRuntimeConfig | None = None
        self._initialized = False

    @property
    def initialized(self) -> bool:
        return self._initialized

    def init_from_config(self, config: MCPRuntimeConfig) -> None:
        self._config = config
        self._tools = self._build_tools(config)
        self._initialized = True

    def reload_from_config(self, config: MCPRuntimeConfig) -> None:
        self.init_from_config(config)

    def close_all(self) -> None:
        self._tools = []
        self._initialized = False

    def list_tools(self) -> list[MCPTool]:
        return list(self._tools)

    @staticmethod
    def _build_tools(config: MCPRuntimeConfig) -> list[MCPTool]:
        if not config.enabled:
            return []

        tools: list[MCPTool] = []
        for server in config.servers:
            for tool in server.tools:
                tools.append(
                    MCPTool(
                        name=tool.name,
                        description=tool.description,
                        risk_level=tool.risk_level or "low",
                        handler=MCPClientManager._build_handler(
                            tool=tool,
                            server_name=server.name,
                        ),
                        server_name=server.name,
                    )
                )
        return tools

    @staticmethod
    def _build_handler(
        *,
        tool: MCPToolConfig,
        server_name: str,
    ) -> MCPHandler:
        def _handler(state: AgentState) -> dict[str, Any]:
            params = _get_action_input(state)
            message = tool.default_message or f"MCP tool '{tool.name}' invoked on server '{server_name}'."
            return {
                "message": message,
                "mcp_server": server_name,
                "mcp_tool": tool.name,
                "input": params,
            }

        return _handler


