from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from .contracts import (
    ProviderAttempt,
    ProviderClient,
    ProviderEndpoint,
    ProviderInvocationError,
    ProviderRoleBinding,
    ProviderSettings,
)
from .langchain_client import LangChainProviderClient
from .settings import ROLE_AGENT, load_provider_settings_from_env


def extract_json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        raw = json.loads(cleaned)
    except json.JSONDecodeError:
        raw = _extract_embedded_json(cleaned)

    if not isinstance(raw, dict):
        raise ProviderInvocationError("model output JSON must be object")
    return raw


def _extract_embedded_json(cleaned: str) -> dict[str, Any]:
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end <= start:
        raise ProviderInvocationError("model output does not contain JSON object")
    candidate = cleaned[start : end + 1]
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise ProviderInvocationError("model output JSON parse failed") from exc
    if not isinstance(parsed, dict):
        raise ProviderInvocationError("model output JSON must be object")
    return parsed


class ProviderClientRegistry:
    def __init__(
        self,
        *,
        client_factory: Callable[[ProviderEndpoint], ProviderClient] | None = None,
    ) -> None:
        self._client_factory = client_factory or LangChainProviderClient
        self._clients: dict[str, ProviderClient] = {}

    def get_client(self, endpoint: ProviderEndpoint) -> ProviderClient:
        client = self._clients.get(endpoint.key)
        if client is not None:
            return client
        created = self._client_factory(endpoint)
        self._clients[endpoint.key] = created
        return created


@dataclass(frozen=True)
class ProviderInvocationResult:
    data: dict[str, Any]
    provider: str
    model: str
    finish_reason: str = ""
    usage: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderTextResult:
    text: str
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
        raw = self._invoke_role_raw(
            role=role,
            system_prompt=system_prompt,
            payload=payload,
            on_token=on_token,
        )
        parsed = extract_json_object(raw["text"])
        return ProviderInvocationResult(
            data=parsed,
            provider=raw["provider"],
            model=raw["model"],
            finish_reason=raw["finish_reason"],
            usage=raw["usage"],
        )

    def invoke_role_text(
        self,
        *,
        role: str,
        system_prompt: str,
        user_message: str,
        on_token: Callable[[str], None] | None = None,
    ) -> ProviderTextResult:
        raw = self._invoke_role_raw(
            role=role,
            system_prompt=system_prompt,
            payload=user_message,
            on_token=on_token,
        )
        return ProviderTextResult(
            text=raw["text"],
            provider=raw["provider"],
            model=raw["model"],
            finish_reason=raw["finish_reason"],
            usage=raw["usage"],
        )

    def _invoke_role_raw(
        self,
        *,
        role: str,
        system_prompt: str,
        payload: dict[str, Any] | str,
        on_token: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
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
                    "system_prompt": system_prompt,
                    "request_payload": payload,
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

                def _forward_reasoning(token: str) -> None:
                    self._emit(
                        "model_reasoning_token",
                        {
                            "role": role,
                            "provider": endpoint.provider,
                            "model": endpoint.model,
                            "token": token,
                        },
                    )

                try:
                    response = client.invoke(
                        system_prompt=system_prompt,
                        payload=payload,
                        on_token=_forward_token if on_token or self._event_listener else None,
                        on_reasoning=_forward_reasoning if self._event_listener else None,
                    )
                except TypeError:
                    try:
                        response = client.invoke(
                            system_prompt=system_prompt,
                            payload=payload,
                            on_token=_forward_token if on_token or self._event_listener else None,
                        )
                    except TypeError:
                        response = client.invoke(
                            system_prompt=system_prompt,
                            payload=payload,
                        )
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
                return {
                    "text": response.text,
                    "provider": endpoint.provider,
                    "model": endpoint.model,
                    "finish_reason": response.finish_reason,
                    "usage": response.usage,
                }
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
    "ProviderInvocationResult",
    "ProviderTextResult",
    "ProviderClientRegistry",
    "ProviderManager",
    "build_default_provider_manager",
    "extract_json_object",
]
