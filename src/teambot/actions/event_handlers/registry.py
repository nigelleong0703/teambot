from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from ...domain.models import AgentState

EventHandler = Callable[[AgentState], dict]


@dataclass(frozen=True)
class EventHandlerManifest:
    name: str
    description: str
    timeout_seconds: int = 0


class EventHandlerRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, EventHandler] = {}
        self._manifests: dict[str, EventHandlerManifest] = {}

    def register(self, manifest: EventHandlerManifest, handler: EventHandler) -> None:
        self._manifests[manifest.name] = manifest
        self._handlers[manifest.name] = handler

    def has_handler(self, name: str) -> bool:
        return name in self._handlers

    def list_manifests(self) -> list[EventHandlerManifest]:
        return list(self._manifests.values())

    def invoke(self, name: str, state: AgentState) -> dict:
        if name not in self._handlers:
            raise KeyError(f"event handler not found: {name}")
        return self._handlers[name](state)

