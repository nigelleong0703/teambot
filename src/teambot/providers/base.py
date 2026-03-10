from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

from .registry import resolve_profile_name


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


@dataclass(frozen=True, init=False)
class ProviderProfileBinding:
    profile: str
    endpoints: list[ProviderEndpoint]
    max_attempts: int = 2

    def __init__(
        self,
        *,
        profile: str | None = None,
        endpoints: list[ProviderEndpoint],
        max_attempts: int = 2,
        role: str | None = None,
    ) -> None:
        resolved = resolve_profile_name(profile or role or "")
        object.__setattr__(self, "profile", resolved)
        object.__setattr__(self, "endpoints", endpoints)
        object.__setattr__(self, "max_attempts", max_attempts)

    @property
    def role(self) -> str:
        return self.profile


@dataclass(frozen=True, init=False)
class ProviderSettings:
    profile_bindings: dict[str, ProviderProfileBinding] = field(default_factory=dict)

    def __init__(
        self,
        *,
        profile_bindings: dict[str, ProviderProfileBinding] | None = None,
        role_bindings: dict[str, ProviderProfileBinding] | None = None,
    ) -> None:
        raw = profile_bindings if profile_bindings is not None else role_bindings or {}
        resolved = {
            resolve_profile_name(key): binding
            for key, binding in raw.items()
        }
        object.__setattr__(self, "profile_bindings", resolved)

    @property
    def role_bindings(self) -> dict[str, ProviderProfileBinding]:
        return self.profile_bindings

    def get_profile_binding(self, profile: str) -> ProviderProfileBinding:
        resolved = resolve_profile_name(profile)
        binding = self.profile_bindings.get(resolved)
        if binding is None:
            raise ProviderConfigError(f"profile binding not found: {resolved}")
        return binding

    def get_role_binding(self, role: str) -> ProviderProfileBinding:
        return self.get_profile_binding(role)


@dataclass(frozen=True)
class NormalizedResponse:
    text: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    finish_reason: str = ""
    usage: dict[str, Any] = field(default_factory=dict)
    raw: Any = None


class ProviderClient(Protocol):
    endpoint: ProviderEndpoint

    def invoke(
        self,
        *,
        system_prompt: str,
        payload: dict[str, Any] | str,
        tools: list[dict[str, Any]] | None = None,
        on_token: Callable[[str], None] | None = None,
        on_reasoning: Callable[[str], None] | None = None,
    ) -> NormalizedResponse:
        ...


@dataclass(frozen=True, init=False)
class ProviderAttempt:
    profile: str
    provider: str
    model: str
    endpoint: str
    error: str

    def __init__(
        self,
        *,
        profile: str | None = None,
        provider: str,
        model: str,
        endpoint: str,
        error: str,
        role: str | None = None,
    ) -> None:
        resolved = resolve_profile_name(profile or role or "")
        object.__setattr__(self, "profile", resolved)
        object.__setattr__(self, "provider", provider)
        object.__setattr__(self, "model", model)
        object.__setattr__(self, "endpoint", endpoint)
        object.__setattr__(self, "error", error)

    @property
    def role(self) -> str:
        return self.profile


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


ProviderRoleBinding = ProviderProfileBinding
