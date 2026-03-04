from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Protocol

from .providers.contracts import ProviderEndpoint, ProviderInvocationError
from .providers.langchain_client import LangChainProviderClient
from .providers.manager import extract_json_object


class AdapterError(RuntimeError):
    pass


class PlannerModelAdapter(Protocol):
    def invoke_json(
        self,
        *,
        system_prompt: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        ...


@dataclass(frozen=True)
class ModelProviderConfig:
    provider: str
    model: str
    api_key: str | None = None
    base_url: str | None = None
    timeout_seconds: int = 20
    temperature: float = 0.0

    def to_endpoint(self) -> ProviderEndpoint:
        return ProviderEndpoint(
            provider=self.provider,
            model=self.model,
            api_key=self.api_key,
            base_url=self.base_url,
            timeout_seconds=self.timeout_seconds,
            temperature=self.temperature,
        )


class LangChainChatAdapter:
    """Compatibility shim. Prefer ProviderManager for new code."""

    def __init__(self, config: ModelProviderConfig) -> None:
        self.config = config
        self._client = LangChainProviderClient(self.config.to_endpoint())

    def invoke_json(
        self,
        *,
        system_prompt: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            response = self._client.invoke(system_prompt=system_prompt, payload=payload)
            return extract_json_object(response.text)
        except ProviderInvocationError as exc:
            raise AdapterError(str(exc)) from exc


def build_config_from_env(
    *,
    prefix: str,
    fallback_prefix: str | None = None,
    default_provider: str = "openai-compatible",
    default_base_url: str = "https://api.openai.com/v1",
    required: bool = False,
) -> ModelProviderConfig | None:
    model = _read_env(f"{prefix}_MODEL", fallback_prefix and f"{fallback_prefix}_MODEL")
    if not model:
        if required:
            raise AdapterError(f"{prefix}_MODEL is required")
        return None

    provider = _read_env(
        f"{prefix}_PROVIDER",
        fallback_prefix and f"{fallback_prefix}_PROVIDER",
    ) or default_provider
    api_key = _read_env(
        f"{prefix}_API_KEY",
        fallback_prefix and f"{fallback_prefix}_API_KEY",
    ) or None
    base_url = _read_env(
        f"{prefix}_BASE_URL",
        fallback_prefix and f"{fallback_prefix}_BASE_URL",
    ) or default_base_url
    timeout_raw = _read_env(
        f"{prefix}_TIMEOUT_SECONDS",
        fallback_prefix and f"{fallback_prefix}_TIMEOUT_SECONDS",
    ) or "20"
    timeout_seconds = int(timeout_raw) if timeout_raw.isdigit() else 20
    return ModelProviderConfig(
        provider=provider,
        model=model,
        api_key=api_key,
        base_url=base_url,
        timeout_seconds=timeout_seconds,
    )


def _read_env(primary: str, fallback: str | None) -> str:
    value = os.getenv(primary, "").strip()
    if value:
        return value
    if fallback:
        return os.getenv(fallback, "").strip()
    return ""
