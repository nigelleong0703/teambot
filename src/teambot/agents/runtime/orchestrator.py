from __future__ import annotations

import os
from dataclasses import dataclass

from ..providers.manager import ProviderManager
from ...plugins.registry import PluginHost
from ..mcp import MCPClientManager, load_mcp_runtime_config, register_mcp_tools
from ..skills.registry import SkillRegistry
from ..skills.runtime_loader import build_runtime_skill_registry
from ..tools.registry import ToolRegistry
from ..tools.runtime_builder import build_runtime_tool_registry


def _env_enabled(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes"}


@dataclass
class RuntimeBundle:
    skill_registry: SkillRegistry
    tool_registry: ToolRegistry
    plugin_host: PluginHost
    mcp_manager: MCPClientManager
    mcp_aliases: dict[str, str]


class RuntimeOrchestrator:
    def __init__(
        self,
        *,
        provider_manager: ProviderManager | None,
        dynamic_skills_dir: str | None,
    ) -> None:
        self._provider_manager = provider_manager
        self._dynamic_skills_dir = dynamic_skills_dir

    def build(self) -> RuntimeBundle:
        skill_registry = build_runtime_skill_registry(
            dynamic_skills_dir=self._dynamic_skills_dir,
        )

        tool_registry = build_runtime_tool_registry(
            profile=os.getenv("TOOLS_PROFILE", "minimal"),
            provider_manager=self._provider_manager,
            namesake_strategy=os.getenv("TOOLS_NAMESAKE_STRATEGY", "skip"),
            enable_echo_tool=_env_enabled("ENABLE_ECHO_TOOL"),
            enable_exec_alias=_env_enabled("ENABLE_EXEC_TOOL"),
        )

        mcp_manager = MCPClientManager()
        mcp_aliases: dict[str, str] = {}
        mcp_config = load_mcp_runtime_config()
        mcp_manager.init_from_config(mcp_config)
        if mcp_config.enabled:
            mcp_aliases = register_mcp_tools(
                registry=tool_registry,
                tools=mcp_manager.list_tools(),
                namesake_strategy=os.getenv("TOOLS_NAMESAKE_STRATEGY", "skip"),
            )

        plugin_host = PluginHost()
        plugin_host.bind_skill_registry(skill_registry)
        plugin_host.bind_tool_registry(tool_registry)

        return RuntimeBundle(
            skill_registry=skill_registry,
            tool_registry=tool_registry,
            plugin_host=plugin_host,
            mcp_manager=mcp_manager,
            mcp_aliases=mcp_aliases,
        )
