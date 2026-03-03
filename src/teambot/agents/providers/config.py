from __future__ import annotations

import json
import os
from typing import Any

from .base import ProviderConfigError, ProviderEndpoint, ProviderRoleBinding, ProviderSettings


ROLE_AGENT = "agent_model"
ROLE_ROUTER = "router_model"


def load_provider_settings_from_env() -> ProviderSettings:
    bindings: dict[str, ProviderRoleBinding] = {}

    agent = _build_role_binding(
        role=ROLE_AGENT,
        role_env="AGENT",
    )
    if agent is not None:
        bindings[ROLE_AGENT] = agent

    router = _build_role_binding(
        role=ROLE_ROUTER,
        role_env="ROUTER",
    )
    if router is not None:
        bindings[ROLE_ROUTER] = router

    return ProviderSettings(role_bindings=bindings)


def _build_role_binding(
    *,
    role: str,
    role_env: str,
) -> ProviderRoleBinding | None:
    primary = _build_primary_endpoint(role_env=role_env)
    fallbacks = _read_fallback_endpoints(role_env=role_env)
    if primary is None and not fallbacks:
        return None

    endpoints: list[ProviderEndpoint] = []
    if primary is not None:
        endpoints.append(primary)
    endpoints.extend(fallbacks)

    max_attempts_raw = _read_env(f"{role_env}_MAX_ATTEMPTS") or "2"
    max_attempts = int(max_attempts_raw) if max_attempts_raw.isdigit() else 2
    return ProviderRoleBinding(
        role=role,
        endpoints=endpoints,
        max_attempts=max(max_attempts, 1),
    )


def _build_primary_endpoint(role_env: str) -> ProviderEndpoint | None:
    model = _read_env(f"{role_env}_MODEL")
    if not model:
        return None

    provider = (
        _read_env(f"{role_env}_PROVIDER")
        or "openai-compatible"
    )
    api_key = _resolve_api_key(role_env=role_env, provider=provider)
    base_url = (
        _read_env(f"{role_env}_BASE_URL")
        or "https://api.openai.com/v1"
    )
    timeout_raw = _read_env(f"{role_env}_TIMEOUT_SECONDS") or "20"
    timeout_seconds = int(timeout_raw) if timeout_raw.isdigit() else 20
    return ProviderEndpoint(
        provider=provider,
        model=model,
        api_key=api_key,
        base_url=base_url,
        timeout_seconds=timeout_seconds,
    )


def _read_fallback_endpoints(role_env: str) -> list[ProviderEndpoint]:
    raw = _read_env(f"{role_env}_FALLBACKS_JSON")
    if not raw:
        return []
    try:
        loaded = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ProviderConfigError(
            f"{role_env}_FALLBACKS_JSON is invalid JSON"
        ) from exc
    if not isinstance(loaded, list):
        raise ProviderConfigError(f"{role_env}_FALLBACKS_JSON must be an array")

    endpoints: list[ProviderEndpoint] = []
    for item in loaded:
        if not isinstance(item, dict):
            raise ProviderConfigError(
                f"{role_env}_FALLBACKS_JSON items must be objects"
            )
        endpoints.append(_endpoint_from_dict(item, role_env))
    return endpoints


def _endpoint_from_dict(raw: dict[str, Any], env_name: str) -> ProviderEndpoint:
    provider = str(raw.get("provider", "")).strip()
    model = str(raw.get("model", "")).strip()
    if not provider or not model:
        raise ProviderConfigError(
            f"{env_name}_FALLBACKS_JSON item requires provider and model"
        )
    timeout_raw = raw.get("timeout_seconds", 20)
    timeout_seconds = int(timeout_raw) if isinstance(timeout_raw, (int, float)) else 20
    temperature_raw = raw.get("temperature", 0.0)
    temperature = (
        float(temperature_raw)
        if isinstance(temperature_raw, (int, float))
        else 0.0
    )
    api_key_raw = raw.get("api_key")
    base_url_raw = raw.get("base_url")
    return ProviderEndpoint(
        provider=provider,
        model=model,
        api_key=str(api_key_raw).strip() if isinstance(api_key_raw, str) else None,
        base_url=str(base_url_raw).strip() if isinstance(base_url_raw, str) else None,
        timeout_seconds=timeout_seconds,
        temperature=temperature,
    )


def _resolve_api_key(*, role_env: str, provider: str) -> str | None:
    direct = _read_env(f"{role_env}_API_KEY")
    if direct:
        return direct

    normalized = provider.strip().lower()
    if normalized == "anthropic":
        return (
            _read_env("ANTHROPIC_AUTH_TOKEN")
            or _read_env("ANTHROPIC_API_KEY")
            or None
        )

    if normalized in {"openai", "openai-compatible", "openai_compatible"}:
        return _read_env("OPENAI_API_KEY") or None

    return None


def _read_env(key: str) -> str:
    value = os.getenv(key, "").strip()
    return value
