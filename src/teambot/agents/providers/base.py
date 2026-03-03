from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Protocol


@dataclass(frozen=True)
class ProviderEndpoint:
    provider: str
    model: str
    api_key: str | None = None
    base_url: str | None = None
    timeout_seconds: int = 20
    temperature: float = 0.0

    @property
    def key(self) -> str:
        return (
            f"{self.provider.lower()}::{self.model}::"
            f"{self.base_url or ''}::{self.timeout_seconds}::{self.temperature}"
        )


@dataclass(frozen=True)
class ProviderRoleBinding:
    role: str
    endpoints: list[ProviderEndpoint]
    max_attempts: int = 2


@dataclass(frozen=True)
class ProviderSettings:
    role_bindings: dict[str, ProviderRoleBinding] = field(default_factory=dict)

    def get_role_binding(self, role: str) -> ProviderRoleBinding:
        binding = self.role_bindings.get(role)
        if binding is None:
            raise ProviderConfigError(f"role binding not found: {role}")
        return binding


@dataclass(frozen=True)
class NormalizedResponse:
    text: str
    finish_reason: str = ""
    usage: dict[str, Any] = field(default_factory=dict)
    raw: Any = None


class ProviderClient(Protocol):
    endpoint: ProviderEndpoint

    def invoke(
        self,
        *,
        system_prompt: str,
        payload: dict[str, Any],
        on_token: Callable[[str], None] | None = None,
    ) -> NormalizedResponse:
        ...


@dataclass(frozen=True)
class ProviderAttempt:
    role: str
    provider: str
    model: str
    endpoint: str
    error: str


class ProviderConfigError(RuntimeError):
    pass


class ProviderInvocationError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        attempts: list[ProviderAttempt] | None = None,
    ) -> None:
        super().__init__(message)
        self.attempts = attempts or []
