from __future__ import annotations

import pytest

from teambot.providers.config import load_provider_settings_from_env
from teambot.providers.registry import (
    PROFILE_AGENT,
    PROFILE_SUMMARY,
    default_base_url_for_provider,
    is_supported_provider,
    normalize_provider_name,
)
from teambot.providers.base import ProviderConfigError


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


def test_model_definitions_and_bindings_add_custom_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "MODEL_DEFINITIONS_JSON",
        '{"extract-fast":{"provider":"anthropic","model":"haiku","timeout_seconds":9}}',
    )
    monkeypatch.setenv(
        "MODEL_PROFILE_BINDINGS_JSON",
        '{"extract":"extract-fast"}',
    )

    settings = load_provider_settings_from_env()
    endpoint = settings.get_profile_binding("extract").endpoints[0]

    assert endpoint.provider == "anthropic"
    assert endpoint.model == "haiku"
    assert endpoint.timeout_seconds == 9


def test_model_profile_bindings_override_builtin_summary_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SUMMARY_MODEL", "summary-env")
    monkeypatch.setenv(
        "MODEL_DEFINITIONS_JSON",
        '{"summary-fast":{"provider":"openai","model":"summary-json"}}',
    )
    monkeypatch.setenv(
        "MODEL_PROFILE_BINDINGS_JSON",
        '{"summary":"summary-fast"}',
    )

    settings = load_provider_settings_from_env()

    assert settings.get_profile_binding(PROFILE_SUMMARY).endpoints[0].model == "summary-json"


def test_model_profile_bindings_preserve_builtin_agent_profile_when_not_overridden(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENT_MODEL", "agent-env")
    monkeypatch.setenv(
        "MODEL_DEFINITIONS_JSON",
        '{"extract-fast":{"provider":"openai-compatible","model":"extract-mini"}}',
    )
    monkeypatch.setenv(
        "MODEL_PROFILE_BINDINGS_JSON",
        '{"extract":"extract-fast"}',
    )

    settings = load_provider_settings_from_env()

    assert settings.get_profile_binding(PROFILE_AGENT).endpoints[0].model == "agent-env"


def test_model_definitions_json_rejects_non_object(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MODEL_DEFINITIONS_JSON", "[]")

    with pytest.raises(ProviderConfigError):
        load_provider_settings_from_env()


def test_model_profile_bindings_json_rejects_non_object(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MODEL_DEFINITIONS_JSON", '{"summary-fast":{"model":"m"}}')
    monkeypatch.setenv("MODEL_PROFILE_BINDINGS_JSON", "[]")

    with pytest.raises(ProviderConfigError):
        load_provider_settings_from_env()


def test_model_profile_bindings_support_multiple_definitions_with_max_attempts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "MODEL_DEFINITIONS_JSON",
        (
            '{"summary-primary":{"provider":"openai-compatible","model":"gpt-main"},'
            '"summary-fallback":{"provider":"anthropic","model":"haiku"}}'
        ),
    )
    monkeypatch.setenv(
        "MODEL_PROFILE_BINDINGS_JSON",
        '{"summary":{"definitions":["summary-primary","summary-fallback"],"max_attempts":2}}',
    )

    settings = load_provider_settings_from_env()
    binding = settings.get_profile_binding(PROFILE_SUMMARY)

    assert [endpoint.model for endpoint in binding.endpoints] == ["gpt-main", "haiku"]
    assert binding.max_attempts == 2


def test_model_profile_bindings_support_model_id_and_model_ids_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "MODEL_DEFINITIONS_JSON",
        (
            '{"agent-main":{"provider":"openai-compatible","model":"gpt-main"},'
            '"agent-fallback":{"provider":"anthropic","model":"haiku"}}'
        ),
    )
    monkeypatch.setenv(
        "MODEL_PROFILE_BINDINGS_JSON",
        (
            '{"agent":{"model_ids":["agent-main","agent-fallback"],"max_attempts":2},'
            '"summary":{"model_id":"agent-fallback"}}'
        ),
    )

    settings = load_provider_settings_from_env()

    agent_binding = settings.get_profile_binding(PROFILE_AGENT)
    summary_binding = settings.get_profile_binding(PROFILE_SUMMARY)

    assert [endpoint.model for endpoint in agent_binding.endpoints] == ["gpt-main", "haiku"]
    assert agent_binding.max_attempts == 2
    assert summary_binding.endpoints[0].model == "haiku"


def test_model_definitions_support_api_key_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CUSTOM_MODEL_KEY", "secret-token")
    monkeypatch.setenv(
        "MODEL_DEFINITIONS_JSON",
        '{"summary-fast":{"provider":"anthropic","model":"haiku","api_key_env":"CUSTOM_MODEL_KEY"}}',
    )
    monkeypatch.setenv("MODEL_PROFILE_BINDINGS_JSON", '{"summary":"summary-fast"}')

    settings = load_provider_settings_from_env()
    endpoint = settings.get_profile_binding(PROFILE_SUMMARY).endpoints[0]

    assert endpoint.api_key == "secret-token"


def test_model_definitions_and_bindings_can_load_from_files(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    definitions_file = tmp_path / "model-definitions.json"
    bindings_file = tmp_path / "model-profile-bindings.json"
    definitions_file.write_text(
        (
            '{"agent_main":{"provider":"anthropic","model":"claude-sonnet","api_key_env":"ANTHROPIC_API_KEY"},'
            '"summary_fast":{"provider":"anthropic","model":"claude-haiku","api_key_env":"ANTHROPIC_API_KEY"}}'
        ),
        encoding="utf-8",
    )
    bindings_file.write_text(
        '{"agent":"agent_main","summary":"summary_fast"}',
        encoding="utf-8",
    )
    monkeypatch.setenv("ANTHROPIC_API_KEY", "file-secret")
    monkeypatch.setenv("MODEL_DEFINITIONS_FILE", str(definitions_file))
    monkeypatch.setenv("MODEL_PROFILE_BINDINGS_FILE", str(bindings_file))

    settings = load_provider_settings_from_env()

    assert settings.get_profile_binding(PROFILE_AGENT).endpoints[0].model == "claude-sonnet"
    assert settings.get_profile_binding(PROFILE_SUMMARY).endpoints[0].api_key == "file-secret"


def test_model_definition_files_override_inline_json(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    definitions_file = tmp_path / "model-definitions.json"
    bindings_file = tmp_path / "model-profile-bindings.json"
    definitions_file.write_text(
        '{"agent_main":{"provider":"anthropic","model":"claude-sonnet"}}',
        encoding="utf-8",
    )
    bindings_file.write_text('{"agent":"agent_main"}', encoding="utf-8")
    monkeypatch.setenv(
        "MODEL_DEFINITIONS_JSON",
        '{"agent_main":{"provider":"openai-compatible","model":"gpt-inline"}}',
    )
    monkeypatch.setenv("MODEL_PROFILE_BINDINGS_JSON", '{"agent":"agent_main"}')
    monkeypatch.setenv("MODEL_DEFINITIONS_FILE", str(definitions_file))
    monkeypatch.setenv("MODEL_PROFILE_BINDINGS_FILE", str(bindings_file))

    settings = load_provider_settings_from_env()

    assert settings.get_profile_binding(PROFILE_AGENT).endpoints[0].model == "claude-sonnet"


def test_runtime_config_file_loads_provider_models_and_profiles(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    runtime_config = tmp_path / "config.json"
    runtime_config.write_text(
        (
            '{"providers":{"models":{"agent_main":{"provider":"anthropic","model":"claude-sonnet","api_key_env":"ANTHROPIC_API_KEY"},'
            '"summary_fast":{"provider":"anthropic","model":"claude-haiku","api_key_env":"ANTHROPIC_API_KEY"}},'
            '"profiles":{"agent":"agent_main","summary":"summary_fast"}}}'
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("ANTHROPIC_API_KEY", "runtime-secret")
    monkeypatch.setenv("RUNTIME_CONFIG_FILE", str(runtime_config))

    settings = load_provider_settings_from_env()

    assert settings.get_profile_binding(PROFILE_AGENT).endpoints[0].model == "claude-sonnet"
    assert settings.get_profile_binding(PROFILE_SUMMARY).endpoints[0].api_key == "runtime-secret"


def test_legacy_model_profiles_json_still_supported_for_compatibility(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "MODEL_PROFILES_JSON",
        '{"extract":{"provider":"anthropic","model":"haiku","timeout_seconds":9}}',
    )

    settings = load_provider_settings_from_env()
    endpoint = settings.get_profile_binding("extract").endpoints[0]

    assert endpoint.provider == "anthropic"
    assert endpoint.model == "haiku"
    assert endpoint.timeout_seconds == 9


def test_canonical_profile_bindings_override_legacy_model_profiles_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "MODEL_PROFILES_JSON",
        '{"summary":{"provider":"openai","model":"legacy-summary"}}',
    )
    monkeypatch.setenv(
        "MODEL_DEFINITIONS_JSON",
        '{"summary-fast":{"provider":"anthropic","model":"canonical-summary"}}',
    )
    monkeypatch.setenv(
        "MODEL_PROFILE_BINDINGS_JSON",
        '{"summary":"summary-fast"}',
    )

    settings = load_provider_settings_from_env()

    assert settings.get_profile_binding(PROFILE_SUMMARY).endpoints[0].model == "canonical-summary"
