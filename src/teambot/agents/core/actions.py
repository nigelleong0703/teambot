from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ...agent_core.contracts import ActionPluginRegistry
from ...domain.models import AgentState
from ..skills.registry import SkillManifest, SkillRegistry
from ..tools.registry import ToolRegistry
from ...plugins.registry import PluginHost


@dataclass(frozen=True)
class ActionSpec:
    name: str
    description: str
    source: str
    risk_level: str = "low"


class ActionRegistry:
    def __init__(
        self,
        *,
        plugin_registry: ActionPluginRegistry | None = None,
        skill_registry: SkillRegistry,
        tool_registry: ToolRegistry | None = None,
    ) -> None:
        if plugin_registry is None:
            host = PluginHost()
            host.bind_skill_registry(skill_registry)
            host.bind_tool_registry(tool_registry)
            plugin_registry = host
        self._plugin_registry = plugin_registry

        self._actions: dict[str, ActionSpec] = {}
        for manifest in self._plugin_registry.list_actions():
            self._actions[manifest.name] = ActionSpec(
                name=manifest.name,
                description=manifest.description,
                source=manifest.source,
                risk_level=manifest.risk_level,
            )

    def has_action(self, name: str) -> bool:
        return name in self._actions

    def list_actions(self) -> list[ActionSpec]:
        return list(self._actions.values())

    def list_manifests(self) -> list[SkillManifest]:
        return [
            SkillManifest(name=a.name, description=a.description)
            for a in self._actions.values()
        ]

    def get_action(self, name: str) -> ActionSpec:
        spec = self._actions.get(name)
        if spec is None:
            raise KeyError(f"action not found: {name}")
        return spec

    def invoke(self, name: str, state: AgentState) -> dict[str, Any]:
        if not self._plugin_registry.has_action(name):
            raise KeyError(f"action not found: {name}")
        output = self._plugin_registry.invoke(name, state)
        if not isinstance(output, dict):
            return {"message": str(output)}
        return output

