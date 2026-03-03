from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from ..models import AgentState


@dataclass(frozen=True)
class ActionManifest:
    name: str
    description: str
    source: str
    risk_level: str = "low"
    timeout_seconds: int = 20
    metadata: dict[str, Any] = field(default_factory=dict)


class ActionPluginRegistry(Protocol):
    def list_actions(self) -> list[ActionManifest]:
        ...

    def has_action(self, name: str) -> bool:
        ...

    def invoke(self, name: str, state: AgentState) -> dict[str, Any]:
        ...


@dataclass(frozen=True)
class ModelInvocationResult:
    data: dict[str, Any]
    provider: str
    model: str
    finish_reason: str = ""
    usage: dict[str, Any] = field(default_factory=dict)


class ModelRoleInvoker(Protocol):
    def has_role(self, role: str) -> bool:
        ...

    def invoke_role_json(
        self,
        *,
        role: str,
        system_prompt: str,
        payload: dict[str, Any],
    ) -> ModelInvocationResult:
        ...
