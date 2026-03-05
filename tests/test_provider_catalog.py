from __future__ import annotations

import pytest

from teambot.agents.providers.config import load_provider_settings_from_env
from teambot.agents.providers.registry import (
    default_base_url_for_provider,
    is_supported_provider,
    normalize_provider_name,
)
from teambot.agents.providers.base import ProviderConfigError


def test_provider_name_normalization() -> None:
    assert normalize_provider_name("openai_compatible") == "openai-compatible"
    assert normalize_provider_name("OPENAI") == "openai"
    assert normalize_provider_name(" anthropic ") == "anthropic"


def test_provider_support_check() -> None:
    assert is_supported_provider("openai-compatible") is True
    assert is_supported_provider("openai") is True
    assert is_supported_provider("anthropic") is True
    assert is_supported_provider("vertexai") is False


def test_anthropic_does_not_force_openai_base_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENT_MODEL", "m")
    monkeypatch.setenv("AGENT_PROVIDER", "anthropic")
    settings = load_provider_settings_from_env()
    endpoint = settings.get_role_binding("agent_model").endpoints[0]
    assert endpoint.base_url is None


def test_invalid_provider_rejected_from_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENT_MODEL", "m")
    monkeypatch.setenv("AGENT_PROVIDER", "unknown-provider")
    with pytest.raises(ProviderConfigError):
        load_provider_settings_from_env()


def test_default_base_url_only_for_openai_compat() -> None:
    assert default_base_url_for_provider("openai") == "https://api.openai.com/v1"
    assert (
        default_base_url_for_provider("openai-compatible")
        == "https://api.openai.com/v1"
    )
    assert default_base_url_for_provider("anthropic") is None
