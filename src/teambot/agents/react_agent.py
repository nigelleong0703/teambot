from __future__ import annotations

import os
from typing import Any, Callable

from .providers.manager import (
    ROLE_AGENT,
    ProviderManager,
    build_default_provider_manager,
)
from .tools.registry import ToolRegistry
from ..domain.models import AgentState
from ..plugins.registry import PluginHost
from .core.graph import AgentCoreRuntime, build_graph
from .core.policy import ExecutionPolicyGate
from .mcp.manager import MCPClientManager
from .runtime.orchestrator import RuntimeOrchestrator
from .skills import SkillRegistry


class TeamBotReactAgent:
    """Runtime owner for TeamBot ReAct execution stack.

    This class encapsulates the CoPaw-style internal runtime assembly:
    tools + skills + MCP -> unified action surface -> ReAct graph.
    """

    def __init__(
        self,
        *,
        provider_manager: ProviderManager | None = None,
        dynamic_skills_dir: str | None = None,
        policy_gate: ExecutionPolicyGate | None = None,
        tools_config_path: str | None = None,
        tools_profile: str | None = None,
        strict_tools_config: bool = False,
    ) -> None:
        self.dynamic_skills_dir = (
            dynamic_skills_dir
            if dynamic_skills_dir is not None
            else (os.getenv("SKILLS_DIR", "").strip() or None)
        )
        self.provider_manager: ProviderManager | None = (
            provider_manager
            if provider_manager is not None
            else build_default_provider_manager()
        )
        self.policy_gate = (
            policy_gate
            if policy_gate is not None
            else ExecutionPolicyGate.from_env()
        )

        self.registry: SkillRegistry
        self.tool_registry: ToolRegistry
        self.plugin_host: PluginHost
        self.mcp_manager: MCPClientManager
        self.mcp_aliases: dict[str, str] = {}
        self.graph: AgentCoreRuntime

        self._orchestrator = RuntimeOrchestrator(
            provider_manager=self.provider_manager,
            dynamic_skills_dir=self.dynamic_skills_dir,
            tools_config_path=tools_config_path,
            tools_profile=tools_profile,
            strict_tools_config=strict_tools_config,
        )
        self.reload_runtime()

    def reload_runtime(self) -> None:
        bundle = self._orchestrator.build()
        self.registry = bundle.skill_registry
        self.tool_registry = bundle.tool_registry
        self.plugin_host = bundle.plugin_host
        self.mcp_manager = bundle.mcp_manager
        self.mcp_aliases = bundle.mcp_aliases
        self.graph = build_graph(
            self.registry,
            tool_registry=self.tool_registry,
            plugin_registry=self.plugin_host,
            policy_gate=self.policy_gate,
        )

    def invoke(self, state: AgentState) -> AgentState:
        return self.graph.invoke(state)

    def set_model_event_listener(
        self,
        listener: Callable[[str, dict[str, Any]], None] | None,
    ) -> None:
        manager = self.provider_manager
        if manager is None or not manager.has_role(ROLE_AGENT):
            return
        manager.set_event_listener(listener)

