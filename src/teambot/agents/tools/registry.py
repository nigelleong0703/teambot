from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from ...domain.models import AgentState

ToolHandler = Callable[[AgentState], dict[str, Any]]


@dataclass(frozen=True)
class ToolManifest:
    name: str
    description: str
    input_schema: dict[str, Any] | None = None
    risk_level: str = "low"
    timeout_seconds: int = 20


@dataclass(frozen=True)
class Tool:
    manifest: ToolManifest
    handler: ToolHandler


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, manifest: ToolManifest, handler: ToolHandler) -> None:
        if manifest.name in self._tools:
            raise ValueError(f"tool already registered: {manifest.name}")
        self._tools[manifest.name] = Tool(manifest=manifest, handler=handler)

    def has(self, name: str) -> bool:
        return name in self._tools

    def require(self, name: str) -> Tool:
        tool = self._tools.get(name)
        if tool is None:
            raise KeyError(f"tool not found: {name}")
        return tool

    def invoke(self, name: str, state: AgentState) -> dict[str, Any]:
        return self.require(name).handler(state)

    def list_manifests(self) -> list[ToolManifest]:
        return [tool.manifest for tool in self._tools.values()]

