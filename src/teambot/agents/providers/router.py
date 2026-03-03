from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Any, Callable

from .base import (
    ProviderAttempt,
    ProviderEndpoint,
    ProviderInvocationError,
    ProviderRoleBinding,
    ProviderSettings,
)
from .config import ROLE_AGENT, ROLE_ROUTER, load_provider_settings_from_env
from .normalize import extract_json_object
from .registry import ProviderClientRegistry


@dataclass(frozen=True)
class ProviderInvocationResult:
    data: dict[str, Any]
    provider: str
    model: str
    finish_reason: str = ""
    usage: dict[str, Any] = field(default_factory=dict)


class ProviderManager:
    def __init__(
        self,
        *,
        settings: ProviderSettings,
        client_registry: ProviderClientRegistry | None = None,
        event_listener: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> None:
        self.settings = settings
        self.client_registry = client_registry or ProviderClientRegistry()
        self._event_listener = event_listener

    @classmethod
    def from_env(cls) -> "ProviderManager | None":
        settings = load_provider_settings_from_env()
        if not settings.role_bindings:
            return None
        return cls(settings=settings)

    def has_role(self, role: str) -> bool:
        return role in self.settings.role_bindings

    def set_event_listener(
        self,
        listener: Callable[[str, dict[str, Any]], None] | None,
    ) -> None:
        self._event_listener = listener

    def _emit(self, event: str, payload: dict[str, Any]) -> None:
        if self._event_listener is None:
            return
        self._event_listener(event, payload)

    def invoke_role_json(
        self,
        *,
        role: str,
        system_prompt: str,
        payload: dict[str, Any],
        on_token: Callable[[str], None] | None = None,
    ) -> ProviderInvocationResult:
        binding = self.settings.get_role_binding(role)
        attempts: list[ProviderAttempt] = []
        candidate_endpoints = self._candidate_endpoints(binding)

        for endpoint in candidate_endpoints:
            client = self.client_registry.get_client(endpoint)
            started_at = time.perf_counter()
            self._emit(
                "model_start",
                {
                    "role": role,
                    "provider": endpoint.provider,
                    "model": endpoint.model,
                    "endpoint": endpoint.base_url or "",
                },
            )
            try:
                def _forward_token(token: str) -> None:
                    self._emit(
                        "model_token",
                        {
                            "role": role,
                            "provider": endpoint.provider,
                            "model": endpoint.model,
                            "token": token,
                        },
                    )
                    if on_token is not None:
                        on_token(token)

                response = client.invoke(
                    system_prompt=system_prompt,
                    payload=payload,
                    on_token=_forward_token if on_token or self._event_listener else None,
                )
                parsed = extract_json_object(response.text)
                elapsed_ms = int((time.perf_counter() - started_at) * 1000)
                self._emit(
                    "model_end",
                    {
                        "role": role,
                        "provider": endpoint.provider,
                        "model": endpoint.model,
                        "duration_ms": elapsed_ms,
                        "usage": response.usage,
                        "finish_reason": response.finish_reason,
                    },
                )
                return ProviderInvocationResult(
                    data=parsed,
                    provider=endpoint.provider,
                    model=endpoint.model,
                    finish_reason=response.finish_reason,
                    usage=response.usage,
                )
            except Exception as exc:
                elapsed_ms = int((time.perf_counter() - started_at) * 1000)
                attempts.append(
                    ProviderAttempt(
                        role=role,
                        provider=endpoint.provider,
                        model=endpoint.model,
                        endpoint=endpoint.base_url or "",
                        error=str(exc),
                    )
                )
                self._emit(
                    "model_error",
                    {
                        "role": role,
                        "provider": endpoint.provider,
                        "model": endpoint.model,
                        "duration_ms": elapsed_ms,
                        "error": str(exc),
                    },
                )

        raise ProviderInvocationError(
            f"all providers failed for role: {role}",
            attempts=attempts,
        )

    def _candidate_endpoints(self, binding: ProviderRoleBinding) -> list[ProviderEndpoint]:
        endpoints = list(binding.endpoints)
        if not endpoints:
            raise ProviderInvocationError(
                f"role has no provider endpoints: {binding.role}",
            )
        return endpoints[: max(binding.max_attempts, 1)]


def build_default_provider_manager() -> ProviderManager | None:
    return ProviderManager.from_env()


__all__ = [
    "ROLE_AGENT",
    "ROLE_ROUTER",
    "ProviderInvocationResult",
    "ProviderManager",
    "build_default_provider_manager",
]
