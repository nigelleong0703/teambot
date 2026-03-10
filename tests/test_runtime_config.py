from __future__ import annotations

import pytest

from teambot.runtime_config import RuntimeConfigError, load_runtime_config


def test_runtime_config_expands_env_templates(monkeypatch, tmp_path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        (
            '{"providers":{"models":{"agent_default":{"provider":"anthropic","model":"claude-sonnet",'
            '"api_key":"${ANTHROPIC_API_KEY}","base_url":"https://example.test/${API_VERSION}"}}}}'
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("RUNTIME_CONFIG_FILE", str(config_path))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "secret-token")
    monkeypatch.setenv("API_VERSION", "v1")

    loaded = load_runtime_config()

    model = loaded["providers"]["models"]["agent_default"]
    assert model["api_key"] == "secret-token"
    assert model["base_url"] == "https://example.test/v1"


def test_runtime_config_raises_on_missing_env_template(monkeypatch, tmp_path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        '{"providers":{"models":{"agent_default":{"api_key":"${MISSING_KEY}"}}}}',
        encoding="utf-8",
    )
    monkeypatch.setenv("RUNTIME_CONFIG_FILE", str(config_path))

    with pytest.raises(RuntimeConfigError):
        load_runtime_config()


def test_runtime_config_supports_escaped_env_template(monkeypatch, tmp_path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        '{"note":"literal $${HOME} placeholder"}',
        encoding="utf-8",
    )
    monkeypatch.setenv("RUNTIME_CONFIG_FILE", str(config_path))

    loaded = load_runtime_config()

    assert loaded["note"] == "literal ${HOME} placeholder"
