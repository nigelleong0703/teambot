from __future__ import annotations

from dataclasses import dataclass

from ..actions.event_handlers.builtin import build_registry as build_event_handler_registry
from ..actions.event_handlers.registry import EventHandlerRegistry
from ..providers.manager import ProviderManager
from ..mcp import MCPClientManager, load_mcp_runtime_config, register_mcp_tools
from ..skills.registry import SkillRegistry
from ..skills.runtime_loader import build_runtime_skill_registry
from ..actions.tools.config import load_runtime_tool_config
from ..actions.tools.registry import ToolRegistry
from ..actions.tools.runtime_builder import build_runtime_tool_registry


@dataclass
class RuntimeBundle:
    event_handler_registry: EventHandlerRegistry
    skill_registry: SkillRegistry
    tool_registry: ToolRegistry
    mcp_manager: MCPClientManager
    mcp_aliases: dict[str, str]


class RuntimeOrchestrator:
    def __init__(
        self,
        *,
        provider_manager: ProviderManager | None,
        dynamic_skills_dir: str | None,
        tools_config_path: str | None = None,
        tools_profile: str | None = None,
        strict_tools_config: bool = False,
    ) -> None:
        self._provider_manager = provider_manager
        self._dynamic_skills_dir = dynamic_skills_dir
        self._tools_config_path = tools_config_path
        self._tools_profile = tools_profile
        self._strict_tools_config = strict_tools_config

    def build(self) -> RuntimeBundle:
        event_handler_registry = build_event_handler_registry()
        skill_registry = build_runtime_skill_registry(
            dynamic_skills_dir=self._dynamic_skills_dir,
        )
        tool_config = load_runtime_tool_config(
            config_path=self._tools_config_path,
            profile_override=self._tools_profile,
            strict_path=self._strict_tools_config,
        )

        tool_registry = build_runtime_tool_registry(
            profile=tool_config.profile,
            provider_manager=self._provider_manager,
            namesake_strategy=tool_config.namesake_strategy,
            enable_echo_tool=tool_config.enable_echo_tool,
            enable_exec_alias=tool_config.enable_exec_alias,
            enable_tools=tool_config.enable_tools,
            disable_tools=tool_config.disable_tools,
        )

        mcp_manager = MCPClientManager()
        mcp_aliases: dict[str, str] = {}
        mcp_config = load_mcp_runtime_config()
        mcp_manager.init_from_config(mcp_config)
        if mcp_config.enabled:
            mcp_aliases = register_mcp_tools(
                registry=tool_registry,
                tools=mcp_manager.list_tools(),
                namesake_strategy=tool_config.namesake_strategy,
            )

        return RuntimeBundle(
            event_handler_registry=event_handler_registry,
            skill_registry=skill_registry,
            tool_registry=tool_registry,
            mcp_manager=mcp_manager,
            mcp_aliases=mcp_aliases,
        )
