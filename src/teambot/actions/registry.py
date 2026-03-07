from __future__ import annotations

from typing import Any

from ..contracts.contracts import ActionManifest, ActionPluginRegistry
from ..actions.event_handlers.registry import EventHandlerRegistry
from ..skills.registry import SkillRegistry
from ..actions.tools.registry import ToolRegistry
from ..domain.models import AgentState


class PluginHost(ActionPluginRegistry):
    """Unified action registry over skill and tool plugins."""

    def __init__(self) -> None:
        self._actions: dict[str, ActionManifest] = {}
        self._event_handler_registry: EventHandlerRegistry | None = None
        self._skill_registry: SkillRegistry | None = None
        self._tool_registry: ToolRegistry | None = None
        self._active_names: set[str] = set()

    def bind_event_handler_registry(self, registry: EventHandlerRegistry) -> None:
        self._event_handler_registry = registry
        for manifest in registry.list_manifests():
            self._actions[manifest.name] = ActionManifest(
                name=manifest.name,
                description=manifest.description,
                source="event_handler",
                timeout_seconds=manifest.timeout_seconds,
                risk_level="low",
            )
            self._active_names.add(manifest.name)

    def bind_skill_registry(self, registry: SkillRegistry) -> None:
        self._skill_registry = registry
        for manifest in registry.list_manifests():
            if manifest.name in self._actions:
                continue
            self._actions[manifest.name] = ActionManifest(
                name=manifest.name,
                description=manifest.description,
                source="skill",
                timeout_seconds=manifest.timeout_seconds,
                risk_level="low",
            )
            self._active_names.add(manifest.name)

    def bind_tool_registry(self, registry: ToolRegistry | None) -> None:
        self._tool_registry = registry
        if registry is None:
            return
        for manifest in registry.list_manifests():
            self._actions[manifest.name] = ActionManifest(
                name=manifest.name,
                description=manifest.description,
                source="tool",
                risk_level=manifest.risk_level,
                timeout_seconds=manifest.timeout_seconds,
                metadata={
                    "input_schema": manifest.input_schema or {"type": "object", "properties": {}}
                },
            )
            self._active_names.add(manifest.name)

    def activate(self, name: str) -> bool:
        if name not in self._actions:
            return False
        self._active_names.add(name)
        return True

    def deactivate(self, name: str) -> bool:
        if name not in self._active_names:
            return False
        self._active_names.remove(name)
        return True

    def list_actions(self) -> list[ActionManifest]:
        return [
            action
            for action in self._actions.values()
            if action.name in self._active_names
        ]

    def has_action(self, name: str) -> bool:
        return name in self._active_names

    def get_action(self, name: str) -> ActionManifest:
        action = self._actions.get(name)
        if action is None or action.name not in self._active_names:
            raise KeyError(f"action not found: {name}")
        return action

    def invoke(self, name: str, state: AgentState) -> dict[str, Any]:
        action = self.get_action(name)
        if action.source == "tool":
            if self._tool_registry is None:
                raise KeyError(f"tool registry unavailable for action: {name}")
            output = self._tool_registry.invoke(name, state)
        elif action.source == "event_handler":
            if self._event_handler_registry is None:
                raise KeyError(f"event handler registry unavailable for action: {name}")
            output = self._event_handler_registry.invoke(name, state)
        else:
            if self._skill_registry is None:
                raise KeyError(f"skill registry unavailable for action: {name}")
            output = self._skill_registry.invoke(name, state)

        if not isinstance(output, dict):
            output = {"message": str(output)}
        output.setdefault("_action_source", action.source)
        output.setdefault("_action_name", action.name)
        return output

