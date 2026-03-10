from __future__ import annotations

PROFILE_AGENT = "agent"
PROFILE_SUMMARY = "summary"
LEGACY_ROLE_AGENT = "agent_model"
LEGACY_ROLE_SUMMARY = "summary_model"

# Backward-compatibility alias for older role-based call sites.
ROLE_AGENT = PROFILE_AGENT

_PROFILE_ALIASES = {
    PROFILE_AGENT: PROFILE_AGENT,
    PROFILE_SUMMARY: PROFILE_SUMMARY,
    LEGACY_ROLE_AGENT: PROFILE_AGENT,
    LEGACY_ROLE_SUMMARY: PROFILE_SUMMARY,
}

_LEGACY_PROFILE_NAMES = {
    PROFILE_AGENT: (LEGACY_ROLE_AGENT,),
    PROFILE_SUMMARY: (LEGACY_ROLE_SUMMARY,),
}


def resolve_profile_name(name: str) -> str:
    normalized = name.strip()
    return _PROFILE_ALIASES.get(normalized, normalized)


def candidate_profile_names(name: str) -> tuple[str, ...]:
    resolved = resolve_profile_name(name)
    return (resolved, *_LEGACY_PROFILE_NAMES.get(resolved, ()))

OPENAI_COMPATIBLE_PROVIDER = "openai-compatible"
OPENAI_PROVIDER = "openai"
ANTHROPIC_PROVIDER = "anthropic"

SUPPORTED_PROVIDERS = (
    OPENAI_COMPATIBLE_PROVIDER,
    OPENAI_PROVIDER,
    ANTHROPIC_PROVIDER,
)

_PROVIDER_ALIASES = {
    "openai_compatible": OPENAI_COMPATIBLE_PROVIDER,
    "openai-compatible": OPENAI_COMPATIBLE_PROVIDER,
    "openai": OPENAI_PROVIDER,
    "anthropic": ANTHROPIC_PROVIDER,
}


def normalize_provider_name(provider: str) -> str:
    normalized = provider.strip().lower().replace("_", "-")
    return _PROVIDER_ALIASES.get(normalized, normalized)


def is_supported_provider(provider: str) -> bool:
    return normalize_provider_name(provider) in SUPPORTED_PROVIDERS


def is_openai_compatible_provider(provider: str) -> bool:
    normalized = normalize_provider_name(provider)
    return normalized in {OPENAI_COMPATIBLE_PROVIDER, OPENAI_PROVIDER}


def is_anthropic_provider(provider: str) -> bool:
    return normalize_provider_name(provider) == ANTHROPIC_PROVIDER


def default_base_url_for_provider(provider: str) -> str | None:
    if is_openai_compatible_provider(provider):
        return "https://api.openai.com/v1"
    return None


def provider_api_key_envs(provider: str) -> tuple[str, ...]:
    normalized = normalize_provider_name(provider)
    if normalized == ANTHROPIC_PROVIDER:
        return ("ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_API_KEY")
    if normalized in {OPENAI_COMPATIBLE_PROVIDER, OPENAI_PROVIDER}:
        return ("OPENAI_API_KEY",)
    return ()
