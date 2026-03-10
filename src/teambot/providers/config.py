from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from ..runtime_config import get_runtime_config_section
from .base import (
    ProviderConfigError,
    ProviderEndpoint,
    ProviderProfileBinding,
    ProviderSettings,
)
from .registry import (
    OPENAI_COMPATIBLE_PROVIDER,
    PROFILE_AGENT,
    PROFILE_SUMMARY,
    SUPPORTED_PROVIDERS,
    resolve_profile_name,
    default_base_url_for_provider,
    is_supported_provider,
    normalize_provider_name,
    provider_api_key_envs,
)


def load_provider_settings_from_env() -> ProviderSettings:
    bindings: dict[str, ProviderProfileBinding] = {}

    agent = _build_profile_binding(
        profile=PROFILE_AGENT,
        env_prefix="AGENT",
    )
    if agent is not None:
        bindings[PROFILE_AGENT] = agent

    summary = _build_profile_binding(
        profile=PROFILE_SUMMARY,
        env_prefix="SUMMARY",
    )
    if summary is not None:
        bindings[PROFILE_SUMMARY] = summary

    model_definitions = _read_model_definitions_json()
    model_definitions.update(_read_model_definitions_file())
    bindings.update(_read_legacy_model_profiles_json())
    bindings.update(_read_model_profile_bindings_json(model_definitions))
    bindings.update(_read_model_profile_bindings_file(model_definitions))

    # Canonical runtime config lives in config/config.json under:
    # providers.models
    # providers.profiles
    #
    # It loads last so the single-file config wins over shortcut and legacy envs.
    runtime_model_definitions = _read_runtime_model_definitions()
    all_model_definitions = dict(model_definitions)
    all_model_definitions.update(runtime_model_definitions)
    runtime_bindings = _read_runtime_profile_bindings(all_model_definitions)
    bindings.update(runtime_bindings)

    return ProviderSettings(profile_bindings=bindings)


def _build_profile_binding(
    *,
    profile: str,
    env_prefix: str,
) -> ProviderProfileBinding | None:
    primary = _build_primary_endpoint(env_prefix=env_prefix)
    fallbacks = _read_fallback_endpoints(env_prefix=env_prefix)
    if primary is None and not fallbacks:
        return None

    endpoints: list[ProviderEndpoint] = []
    if primary is not None:
        endpoints.append(primary)
    endpoints.extend(fallbacks)

    max_attempts_raw = _read_env(f"{env_prefix}_MAX_ATTEMPTS") or "2"
    max_attempts = int(max_attempts_raw) if max_attempts_raw.isdigit() else 2
    return ProviderProfileBinding(
        profile=profile,
        endpoints=endpoints,
        max_attempts=max(max_attempts, 1),
    )


def _read_legacy_model_profiles_json() -> dict[str, ProviderProfileBinding]:
    raw = _read_env("MODEL_PROFILES_JSON")
    if not raw:
        return {}
    try:
        loaded = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ProviderConfigError("MODEL_PROFILES_JSON is invalid JSON") from exc
    if not isinstance(loaded, dict):
        raise ProviderConfigError("MODEL_PROFILES_JSON must be an object")

    bindings: dict[str, ProviderProfileBinding] = {}
    for profile_name, item in loaded.items():
        if not isinstance(profile_name, str) or not profile_name.strip():
            raise ProviderConfigError("MODEL_PROFILES_JSON keys must be non-empty strings")
        if not isinstance(item, dict):
            raise ProviderConfigError("MODEL_PROFILES_JSON values must be objects")
        binding = _profile_binding_from_legacy_dict(profile_name, item)
        if binding is not None:
            bindings[binding.profile] = binding
    return bindings


def _read_model_definitions_json() -> dict[str, ProviderEndpoint]:
    raw = _read_env("MODEL_DEFINITIONS_JSON")
    if not raw:
        return {}
    try:
        loaded = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ProviderConfigError("MODEL_DEFINITIONS_JSON is invalid JSON") from exc
    if not isinstance(loaded, dict):
        raise ProviderConfigError("MODEL_DEFINITIONS_JSON must be an object")

    model_definitions: dict[str, ProviderEndpoint] = {}
    for model_id, item in loaded.items():
        if not isinstance(model_id, str) or not model_id.strip():
            raise ProviderConfigError("MODEL_DEFINITIONS_JSON keys must be non-empty strings")
        if not isinstance(item, dict):
            raise ProviderConfigError("MODEL_DEFINITIONS_JSON values must be objects")
        endpoint = _endpoint_from_config_dict(item, env_name=f"MODEL_DEFINITIONS_JSON[{model_id}]")
        if endpoint is None:
            raise ProviderConfigError(f"MODEL_DEFINITIONS_JSON[{model_id}] requires model")
        model_definitions[model_id.strip()] = endpoint
    return model_definitions


def _read_model_definitions_file() -> dict[str, ProviderEndpoint]:
    loaded = _read_json_object_file("MODEL_DEFINITIONS_FILE")
    if loaded is None:
        return {}

    model_definitions: dict[str, ProviderEndpoint] = {}
    for model_id, item in loaded.items():
        if not isinstance(model_id, str) or not model_id.strip():
            raise ProviderConfigError("MODEL_DEFINITIONS_FILE keys must be non-empty strings")
        if not isinstance(item, dict):
            raise ProviderConfigError("MODEL_DEFINITIONS_FILE values must be objects")
        endpoint = _endpoint_from_config_dict(item, env_name=f"MODEL_DEFINITIONS_FILE[{model_id}]")
        if endpoint is None:
            raise ProviderConfigError(f"MODEL_DEFINITIONS_FILE[{model_id}] requires model")
        model_definitions[model_id.strip()] = endpoint
    return model_definitions


def _read_runtime_model_definitions() -> dict[str, ProviderEndpoint]:
    providers = get_runtime_config_section("providers")
    loaded = providers.get("models")
    if not isinstance(loaded, dict):
        return {}

    model_definitions: dict[str, ProviderEndpoint] = {}
    for model_id, item in loaded.items():
        if not isinstance(model_id, str) or not model_id.strip():
            raise ProviderConfigError("runtime providers.models keys must be non-empty strings")
        if not isinstance(item, dict):
            raise ProviderConfigError("runtime providers.models values must be objects")
        endpoint = _endpoint_from_config_dict(item, env_name=f"providers.models[{model_id}]")
        if endpoint is None:
            raise ProviderConfigError(f"providers.models[{model_id}] requires model")
        model_definitions[model_id.strip()] = endpoint
    return model_definitions


def _read_model_profile_bindings_json(
    model_definitions: dict[str, ProviderEndpoint],
) -> dict[str, ProviderProfileBinding]:
    raw = _read_env("MODEL_PROFILE_BINDINGS_JSON")
    if not raw:
        return {}
    try:
        loaded = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ProviderConfigError("MODEL_PROFILE_BINDINGS_JSON is invalid JSON") from exc
    if not isinstance(loaded, dict):
        raise ProviderConfigError("MODEL_PROFILE_BINDINGS_JSON must be an object")

    bindings: dict[str, ProviderProfileBinding] = {}
    for profile_name, item in loaded.items():
        if not isinstance(profile_name, str) or not profile_name.strip():
            raise ProviderConfigError("MODEL_PROFILE_BINDINGS_JSON keys must be non-empty strings")
        binding = _binding_from_model_definitions(
            profile_name=profile_name,
            raw=item,
            model_definitions=model_definitions,
        )
        bindings[binding.profile] = binding
    return bindings


def _read_model_profile_bindings_file(
    model_definitions: dict[str, ProviderEndpoint],
) -> dict[str, ProviderProfileBinding]:
    loaded = _read_json_object_file("MODEL_PROFILE_BINDINGS_FILE")
    if loaded is None:
        return {}

    bindings: dict[str, ProviderProfileBinding] = {}
    for profile_name, item in loaded.items():
        if not isinstance(profile_name, str) or not profile_name.strip():
            raise ProviderConfigError("MODEL_PROFILE_BINDINGS_FILE keys must be non-empty strings")
        binding = _binding_from_model_definitions(
            profile_name=profile_name,
            raw=item,
            model_definitions=model_definitions,
        )
        bindings[binding.profile] = binding
    return bindings


def _read_runtime_profile_bindings(
    model_definitions: dict[str, ProviderEndpoint],
) -> dict[str, ProviderProfileBinding]:
    providers = get_runtime_config_section("providers")
    loaded = providers.get("profiles")
    if not isinstance(loaded, dict):
        return {}

    bindings: dict[str, ProviderProfileBinding] = {}
    for profile_name, item in loaded.items():
        if not isinstance(profile_name, str) or not profile_name.strip():
            raise ProviderConfigError("runtime providers.profiles keys must be non-empty strings")
        binding = _binding_from_model_definitions(
            profile_name=profile_name,
            raw=item,
            model_definitions=model_definitions,
        )
        bindings[binding.profile] = binding
    return bindings


def _binding_from_model_definitions(
    *,
    profile_name: str,
    raw: Any,
    model_definitions: dict[str, ProviderEndpoint],
) -> ProviderProfileBinding:
    profile = resolve_profile_name(profile_name)
    model_ids, max_attempts = _parse_binding_value(profile_name, raw)
    endpoints: list[ProviderEndpoint] = []
    for model_id in model_ids:
        endpoint = model_definitions.get(model_id)
        if endpoint is None:
            raise ProviderConfigError(
                f"MODEL_PROFILE_BINDINGS_JSON[{profile_name}] references unknown model_id '{model_id}'"
            )
        endpoints.append(endpoint)
    return ProviderProfileBinding(
        profile=profile,
        endpoints=endpoints,
        max_attempts=max(max_attempts, 1),
    )


def _parse_binding_value(profile_name: str, raw: Any) -> tuple[list[str], int]:
    if isinstance(raw, str) and raw.strip():
        return [raw.strip()], 2
    if isinstance(raw, list):
        model_ids = [str(item).strip() for item in raw if str(item).strip()]
        if not model_ids:
            raise ProviderConfigError(
                f"MODEL_PROFILE_BINDINGS_JSON[{profile_name}] list must contain at least one model_id"
            )
        return model_ids, 2
    if isinstance(raw, dict):
        model_ids: list[str]
        if isinstance(raw.get("model_id"), str) and str(raw["model_id"]).strip():
            model_ids = [str(raw["model_id"]).strip()]
        elif isinstance(raw.get("definition"), str) and str(raw["definition"]).strip():
            model_ids = [str(raw["definition"]).strip()]
        else:
            model_ids_raw = raw.get("model_ids")
            if model_ids_raw is None:
                model_ids_raw = raw.get("definitions", [])
            if not isinstance(model_ids_raw, list):
                raise ProviderConfigError(
                    f"MODEL_PROFILE_BINDINGS_JSON[{profile_name}].model_ids must be an array"
                )
            model_ids = [str(item).strip() for item in model_ids_raw if str(item).strip()]
        if not model_ids:
            raise ProviderConfigError(
                f"MODEL_PROFILE_BINDINGS_JSON[{profile_name}] requires model_id or model_ids"
            )
        max_attempts_raw = raw.get("max_attempts", 2)
        max_attempts = (
            int(max_attempts_raw)
            if isinstance(max_attempts_raw, (int, float, str)) and str(max_attempts_raw).isdigit()
            else 2
        )
        return model_ids, max_attempts
    raise ProviderConfigError(
        f"MODEL_PROFILE_BINDINGS_JSON[{profile_name}] must be a string, array, or object"
    )


def _profile_binding_from_legacy_dict(
    profile_name: str,
    raw: dict[str, Any],
) -> ProviderProfileBinding | None:
    profile = resolve_profile_name(profile_name)
    endpoints: list[ProviderEndpoint] = []

    primary = _endpoint_from_config_dict(raw, env_name=f"MODEL_PROFILES_JSON[{profile_name}]")
    if primary is not None:
        endpoints.append(primary)

    fallbacks_raw = raw.get("fallbacks", [])
    if fallbacks_raw not in ({}, None, []):
        if not isinstance(fallbacks_raw, list):
            raise ProviderConfigError(f"MODEL_PROFILES_JSON[{profile_name}].fallbacks must be an array")
        for item in fallbacks_raw:
            if not isinstance(item, dict):
                raise ProviderConfigError(
                    f"MODEL_PROFILES_JSON[{profile_name}].fallbacks items must be objects"
                )
            endpoints.append(_endpoint_from_dict(item, f"MODEL_PROFILES_JSON[{profile_name}]"))

    if not endpoints:
        return None

    max_attempts_raw = raw.get("max_attempts", 2)
    max_attempts = int(max_attempts_raw) if isinstance(max_attempts_raw, (int, float, str)) and str(max_attempts_raw).isdigit() else 2
    return ProviderProfileBinding(
        profile=profile,
        endpoints=endpoints,
        max_attempts=max(max_attempts, 1),
    )


def _endpoint_from_config_dict(
    raw: dict[str, Any],
    *,
    env_name: str,
) -> ProviderEndpoint | None:
    model = str(raw.get("model", "")).strip()
    if not model:
        return None
    provider = normalize_provider_name(str(raw.get("provider", "")).strip() or OPENAI_COMPATIBLE_PROVIDER)
    if not is_supported_provider(provider):
        raise ProviderConfigError(
            f"{env_name}.provider unsupported value '{provider}'. supported={', '.join(SUPPORTED_PROVIDERS)}"
        )
    timeout_raw = raw.get("timeout_seconds", 20)
    timeout_seconds = int(timeout_raw) if isinstance(timeout_raw, (int, float, str)) and str(timeout_raw).isdigit() else 20
    temperature_raw = raw.get("temperature", 0.0)
    temperature = float(temperature_raw) if isinstance(temperature_raw, (int, float)) else 0.0
    api_key = _resolve_definition_api_key(raw=raw, provider=provider)
    base_url_raw = raw.get("base_url")
    return ProviderEndpoint(
        provider=provider,
        model=model,
        api_key=api_key,
        base_url=(
            str(base_url_raw).strip()
            if isinstance(base_url_raw, str)
            else default_base_url_for_provider(provider) or None
        ),
        timeout_seconds=timeout_seconds,
        temperature=temperature,
    )


def _resolve_definition_api_key(
    *,
    raw: dict[str, Any],
    provider: str,
) -> str | None:
    api_key_raw = raw.get("api_key")
    if isinstance(api_key_raw, str) and api_key_raw.strip():
        return api_key_raw.strip()

    api_key_env_raw = raw.get("api_key_env")
    if isinstance(api_key_env_raw, str) and api_key_env_raw.strip():
        value = _read_env(api_key_env_raw.strip())
        if value:
            return value

    for env_name in provider_api_key_envs(provider):
        value = _read_env(env_name)
        if value:
            return value
    return None


def _build_primary_endpoint(env_prefix: str) -> ProviderEndpoint | None:
    model = _read_env(f"{env_prefix}_MODEL")
    if not model:
        return None

    provider = normalize_provider_name(
        _read_env(f"{env_prefix}_PROVIDER")
        or OPENAI_COMPATIBLE_PROVIDER
    )
    if not is_supported_provider(provider):
        raise ProviderConfigError(
            f"{env_prefix}_PROVIDER unsupported value '{provider}'. "
            f"supported={', '.join(SUPPORTED_PROVIDERS)}"
        )
    api_key = _resolve_api_key(env_prefix=env_prefix, provider=provider)
    base_url = (
        _read_env(f"{env_prefix}_BASE_URL")
        or default_base_url_for_provider(provider)
        or None
    )
    timeout_raw = _read_env(f"{env_prefix}_TIMEOUT_SECONDS") or "20"
    timeout_seconds = int(timeout_raw) if timeout_raw.isdigit() else 20
    return ProviderEndpoint(
        provider=provider,
        model=model,
        api_key=api_key,
        base_url=base_url,
        timeout_seconds=timeout_seconds,
    )


def _read_fallback_endpoints(env_prefix: str) -> list[ProviderEndpoint]:
    raw = _read_env(f"{env_prefix}_FALLBACKS_JSON")
    if not raw:
        return []
    try:
        loaded = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ProviderConfigError(
            f"{env_prefix}_FALLBACKS_JSON is invalid JSON"
        ) from exc
    if not isinstance(loaded, list):
        raise ProviderConfigError(f"{env_prefix}_FALLBACKS_JSON must be an array")

    endpoints: list[ProviderEndpoint] = []
    for item in loaded:
        if not isinstance(item, dict):
            raise ProviderConfigError(
                f"{env_prefix}_FALLBACKS_JSON items must be objects"
            )
        endpoints.append(_endpoint_from_dict(item, env_prefix))
    return endpoints


def _endpoint_from_dict(raw: dict[str, Any], env_name: str) -> ProviderEndpoint:
    provider = normalize_provider_name(str(raw.get("provider", "")).strip())
    model = str(raw.get("model", "")).strip()
    if not provider or not model:
        raise ProviderConfigError(
            f"{env_name}_FALLBACKS_JSON item requires provider and model"
        )
    if not is_supported_provider(provider):
        raise ProviderConfigError(
            f"{env_name}_FALLBACKS_JSON item has unsupported provider '{provider}'. "
            f"supported={', '.join(SUPPORTED_PROVIDERS)}"
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


def _resolve_api_key(*, env_prefix: str, provider: str) -> str | None:
    direct = _read_env(f"{env_prefix}_API_KEY")
    if direct:
        return direct

    for env_name in provider_api_key_envs(provider):
        value = _read_env(env_name)
        if value:
            return value
    return None


def _read_env(key: str) -> str:
    value = os.getenv(key, "").strip()
    return value


def _read_json_object_file(env_key: str) -> dict[str, Any] | None:
    raw_path = _read_env(env_key)
    if not raw_path:
        return None

    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()

    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ProviderConfigError(f"{env_key} file not found: {path}") from exc
    except OSError as exc:
        raise ProviderConfigError(f"{env_key} could not be read: {path}") from exc

    try:
        loaded = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ProviderConfigError(f"{env_key} is invalid JSON") from exc
    if not isinstance(loaded, dict):
        raise ProviderConfigError(f"{env_key} must point to a JSON object file")
    return loaded
