from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from ..contracts.contracts import ModelToolCall, ModelToolInvocationResult, ModelToolSpec
from .base import (
    ProviderAttempt,
    ProviderClient,
    ProviderEndpoint,
    ProviderInvocationError,
    ProviderProfileBinding,
    ProviderSettings,
)
from .clients.langchain import LangChainProviderClient
from .config import load_provider_settings_from_env
from .registry import PROFILE_AGENT, PROFILE_SUMMARY, ROLE_AGENT, resolve_profile_name


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
        if not settings.profile_bindings:
            return None
        return cls(settings=settings)

    def has_profile(self, profile: str) -> bool:
        return resolve_profile_name(profile) in self.settings.profile_bindings

    def has_role(self, role: str) -> bool:
        return self.has_profile(role)

    def set_event_listener(
        self,
        listener: Callable[[str, dict[str, Any]], None] | None,
    ) -> None:
        self._event_listener = listener

    def _emit(self, event: str, payload: dict[str, Any]) -> None:
        if self._event_listener is None:
            return
        self._event_listener(event, payload)

    def invoke_profile_json(
        self,
        *,
        profile: str,
        system_prompt: str,
        payload: dict[str, Any],
        on_token: Callable[[str], None] | None = None,
    ) -> ProviderInvocationResult:
        raw = self._invoke_profile_raw(
            profile=resolve_profile_name(profile),
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

    def invoke_profile_text(
        self,
        *,
        profile: str,
        system_prompt: str,
        user_message: str,
        on_token: Callable[[str], None] | None = None,
    ) -> ProviderTextResult:
        raw = self._invoke_profile_raw(
            profile=resolve_profile_name(profile),
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

    def invoke_profile_tools(
        self,
        *,
        profile: str,
        system_prompt: str,
        payload: dict[str, Any],
        tools: list[ModelToolSpec],
        on_token: Callable[[str], None] | None = None,
    ) -> ModelToolInvocationResult:
        tool_payload = [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.input_schema,
            }
            for tool in tools
        ]
        raw = self._invoke_profile_raw(
            profile=resolve_profile_name(profile),
            system_prompt=system_prompt,
            payload=payload,
            tools=tool_payload,
            on_token=on_token,
        )
        parsed_tool_calls: list[ModelToolCall] = []
        for item in raw.get("tool_calls", []):
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            if not name:
                continue
            arguments_raw = item.get("arguments", {})
            arguments = arguments_raw if isinstance(arguments_raw, dict) else {}
            parsed_tool_calls.append(
                ModelToolCall(
                    name=name,
                    arguments=arguments,
                    call_id=str(item.get("id", "")).strip(),
                )
            )
        return ModelToolInvocationResult(
            text=str(raw.get("text", "")),
            tool_calls=parsed_tool_calls,
            provider=str(raw.get("provider", "")),
            model=str(raw.get("model", "")),
            finish_reason=str(raw.get("finish_reason", "")),
            usage=raw.get("usage", {}) if isinstance(raw.get("usage"), dict) else {},
        )

    def invoke_role_json(
        self,
        *,
        role: str,
        system_prompt: str,
        payload: dict[str, Any],
        on_token: Callable[[str], None] | None = None,
    ) -> ProviderInvocationResult:
        return self.invoke_profile_json(
            profile=role,
            system_prompt=system_prompt,
            payload=payload,
            on_token=on_token,
        )

    def invoke_role_text(
        self,
        *,
        role: str,
        system_prompt: str,
        user_message: str,
        on_token: Callable[[str], None] | None = None,
    ) -> ProviderTextResult:
        return self.invoke_profile_text(
            profile=role,
            system_prompt=system_prompt,
            user_message=user_message,
            on_token=on_token,
        )

    def invoke_role_tools(
        self,
        *,
        role: str,
        system_prompt: str,
        payload: dict[str, Any],
        tools: list[ModelToolSpec],
        on_token: Callable[[str], None] | None = None,
    ) -> ModelToolInvocationResult:
        return self.invoke_profile_tools(
            profile=role,
            system_prompt=system_prompt,
            payload=payload,
            tools=tools,
            on_token=on_token,
        )

    def _invoke_profile_raw(
        self,
        *,
        profile: str,
        system_prompt: str,
        payload: dict[str, Any] | str,
        tools: list[dict[str, Any]] | None = None,
        on_token: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        profile = resolve_profile_name(profile)
        binding = self.settings.get_profile_binding(profile)
        attempts: list[ProviderAttempt] = []
        candidate_endpoints = self._candidate_endpoints(binding)

        for endpoint in candidate_endpoints:
            client = self.client_registry.get_client(endpoint)
            started_at = time.perf_counter()
            self._emit(
                "model_start",
                {
                    "profile": profile,
                    "role": profile,
                    "provider": endpoint.provider,
                    "model": endpoint.model,
                    "endpoint": endpoint.base_url or "",
                    "system_prompt": system_prompt,
                    "request_payload": payload,
                    "tools": tools or [],
                },
            )
            try:

                def _forward_token(token: str) -> None:
                    self._emit(
                        "model_token",
                        {
                            "profile": profile,
                            "role": profile,
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
                            "profile": profile,
                            "role": profile,
                            "provider": endpoint.provider,
                            "model": endpoint.model,
                            "token": token,
                        },
                    )

                invoke_variants = [
                    {
                        "system_prompt": system_prompt,
                        "payload": payload,
                        "tools": tools,
                        "on_token": _forward_token if on_token or self._event_listener else None,
                        "on_reasoning": _forward_reasoning if self._event_listener else None,
                    },
                    {
                        "system_prompt": system_prompt,
                        "payload": payload,
                        "tools": tools,
                        "on_token": _forward_token if on_token or self._event_listener else None,
                    },
                    {
                        "system_prompt": system_prompt,
                        "payload": payload,
                        "tools": tools,
                    },
                    {
                        "system_prompt": system_prompt,
                        "payload": payload,
                        "on_token": _forward_token if on_token or self._event_listener else None,
                    },
                    {
                        "system_prompt": system_prompt,
                        "payload": payload,
                    },
                ]

                last_type_error: TypeError | None = None
                response = None
                for kwargs in invoke_variants:
                    try:
                        response = client.invoke(**kwargs)
                        break
                    except TypeError as exc:
                        last_type_error = exc
                        continue
                if response is None:
                    if last_type_error is not None:
                        raise last_type_error
                    raise ProviderInvocationError("provider client invoke returned no response")
                elapsed_ms = int((time.perf_counter() - started_at) * 1000)
                self._emit(
                    "model_end",
                    {
                        "profile": profile,
                        "role": profile,
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
                    "tool_calls": response.tool_calls,
                }
            except Exception as exc:
                elapsed_ms = int((time.perf_counter() - started_at) * 1000)
                attempts.append(
                    ProviderAttempt(
                        profile=profile,
                        provider=endpoint.provider,
                        model=endpoint.model,
                        endpoint=endpoint.base_url or "",
                        error=str(exc),
                    )
                )
                self._emit(
                    "model_error",
                    {
                        "profile": profile,
                        "role": profile,
                        "provider": endpoint.provider,
                        "model": endpoint.model,
                        "duration_ms": elapsed_ms,
                        "error": str(exc),
                    },
                )

        raise ProviderInvocationError(
            f"all providers failed for profile: {profile}",
            attempts=attempts,
        )

    def _candidate_endpoints(self, binding: ProviderProfileBinding) -> list[ProviderEndpoint]:
        endpoints = list(binding.endpoints)
        if not endpoints:
            raise ProviderInvocationError(
                f"profile has no provider endpoints: {binding.profile}",
            )
        return endpoints[: max(binding.max_attempts, 1)]


def build_default_provider_manager() -> ProviderManager | None:
    return ProviderManager.from_env()


__all__ = [
    "PROFILE_AGENT",
    "PROFILE_SUMMARY",
    "ROLE_AGENT",
    "ProviderInvocationResult",
    "ProviderTextResult",
    "ProviderClientRegistry",
    "ProviderManager",
    "build_default_provider_manager",
    "extract_json_object",
]
