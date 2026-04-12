# tests/test_thinking_budget.py
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from teambot.providers.base import ProviderConfigError, ProviderEndpoint
from teambot.providers.clients.native import (
    NativeProviderClient,
    _THINKING_BUDGET_MAP,
    _THINKING_MAX_TOKENS_MAP,
)
from teambot.providers.config import (
    _endpoint_from_dict,
    load_provider_settings_from_env,
)


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------

def _make_endpoint(**kwargs) -> ProviderEndpoint:
    defaults = dict(provider="anthropic", model="claude-opus-4-6")
    defaults.update(kwargs)
    return ProviderEndpoint(**defaults)


def _make_client(thinking_effort: str | None = None) -> NativeProviderClient:
    ep = _make_endpoint(api_key="test-key", thinking_effort=thinking_effort)
    return NativeProviderClient(ep)


# -------------------------------------------------------------------
# ProviderEndpoint field + key
# -------------------------------------------------------------------

def test_thinking_effort_defaults_to_none() -> None:
    ep = _make_endpoint()
    assert ep.thinking_effort is None


def test_thinking_effort_stored_correctly() -> None:
    ep = _make_endpoint(thinking_effort="high")
    assert ep.thinking_effort == "high"


def test_key_includes_thinking_effort_when_set() -> None:
    ep = _make_endpoint(thinking_effort="high")
    assert "high" in ep.key


def test_key_differs_between_effort_levels() -> None:
    ep_none = _make_endpoint()
    ep_high = _make_endpoint(thinking_effort="high")
    ep_low = _make_endpoint(thinking_effort="low")
    assert ep_none.key != ep_high.key
    assert ep_high.key != ep_low.key


# -------------------------------------------------------------------
# Config loaders
# -------------------------------------------------------------------

def test_endpoint_from_config_dict_loads_thinking_effort(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "MODEL_DEFINITIONS_JSON",
        '{"thinking-model":{"provider":"anthropic","model":"claude-opus-4-6",'
        '"thinking_effort":"high"}}',
    )
    monkeypatch.setenv("MODEL_PROFILE_BINDINGS_JSON", '{"agent":"thinking-model"}')

    settings = load_provider_settings_from_env()
    endpoint = settings.get_profile_binding("agent").endpoints[0]

    assert endpoint.thinking_effort == "high"


def test_endpoint_from_config_dict_thinking_effort_none_when_omitted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "MODEL_DEFINITIONS_JSON",
        '{"plain-model":{"provider":"anthropic","model":"claude-opus-4-6"}}',
    )
    monkeypatch.setenv("MODEL_PROFILE_BINDINGS_JSON", '{"agent":"plain-model"}')

    settings = load_provider_settings_from_env()
    endpoint = settings.get_profile_binding("agent").endpoints[0]

    assert endpoint.thinking_effort is None


def test_endpoint_from_dict_loads_thinking_effort() -> None:
    raw = {
        "provider": "anthropic",
        "model": "claude-opus-4-6",
        "thinking_effort": "medium",
    }
    ep = _endpoint_from_dict(raw, "TEST")
    assert ep.thinking_effort == "medium"


def test_build_primary_endpoint_reads_thinking_effort_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENT_MODEL", "claude-opus-4-6")
    monkeypatch.setenv("AGENT_PROVIDER", "anthropic")
    monkeypatch.setenv("AGENT_THINKING_EFFORT", "xhigh")

    settings = load_provider_settings_from_env()
    endpoint = settings.get_profile_binding("agent").endpoints[0]

    assert endpoint.thinking_effort == "xhigh"


def test_unknown_effort_raises_at_config_load(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "MODEL_DEFINITIONS_JSON",
        '{"bad-model":{"provider":"anthropic","model":"claude-opus-4-6",'
        '"thinking_effort":"turbo"}}',
    )
    monkeypatch.setenv("MODEL_PROFILE_BINDINGS_JSON", '{"agent":"bad-model"}')

    with pytest.raises(ProviderConfigError, match="thinking_effort"):
        load_provider_settings_from_env()


# -------------------------------------------------------------------
# NativeProviderClient — budget maps
# -------------------------------------------------------------------

def test_thinking_budget_map_values() -> None:
    assert _THINKING_BUDGET_MAP["low"] == 4096
    assert _THINKING_BUDGET_MAP["medium"] == 8192
    assert _THINKING_BUDGET_MAP["high"] == 16384
    assert _THINKING_BUDGET_MAP["xhigh"] == 32768
    for effort in ("low", "medium", "high", "xhigh"):
        assert _THINKING_MAX_TOKENS_MAP[effort] > _THINKING_BUDGET_MAP[effort], (
            f"max_tokens must be > budget_tokens for effort={effort}"
        )


# -------------------------------------------------------------------
# NativeProviderClient — no injection when thinking_effort is None
# -------------------------------------------------------------------

def test_no_thinking_effort_no_injection() -> None:
    client = _make_client()
    captured: dict = {}

    mock_response = MagicMock()
    mock_response.content = []
    mock_response.usage = None
    mock_response.stop_reason = "end_turn"

    def fake_create(**kwargs):
        captured.update(kwargs)
        return mock_response

    mock_anthropic = MagicMock()
    mock_anthropic.messages.create.side_effect = fake_create

    with patch("anthropic.Anthropic", return_value=mock_anthropic):
        client._invoke_anthropic_chat(
            system_prompt="sys",
            messages=[{"role": "user", "content": "hi"}],
            tools=None,
            on_token=None,
            on_reasoning=None,
        )

    assert "thinking" not in captured
    assert captured["temperature"] == 0.0


# -------------------------------------------------------------------
# NativeProviderClient — injection: _invoke_anthropic_chat non-streaming
# -------------------------------------------------------------------

def test_thinking_effort_injects_thinking_block() -> None:
    client = _make_client(thinking_effort="high")
    captured: dict = {}

    mock_response = MagicMock()
    mock_response.content = []
    mock_response.usage = None
    mock_response.stop_reason = "end_turn"

    def fake_create(**kwargs):
        captured.update(kwargs)
        return mock_response

    mock_anthropic = MagicMock()
    mock_anthropic.messages.create.side_effect = fake_create

    with patch("anthropic.Anthropic", return_value=mock_anthropic):
        client._invoke_anthropic_chat(
            system_prompt="sys",
            messages=[{"role": "user", "content": "hi"}],
            tools=None,
            on_token=None,
            on_reasoning=None,
        )

    assert captured["thinking"] == {"type": "enabled", "budget_tokens": 16384}
    assert captured["temperature"] == 1
    assert captured["max_tokens"] == _THINKING_MAX_TOKENS_MAP["high"]


# -------------------------------------------------------------------
# NativeProviderClient — injection: _invoke_anthropic (single-turn) non-streaming
# -------------------------------------------------------------------

def test_thinking_effort_injects_thinking_block_invoke_anthropic() -> None:
    client = _make_client(thinking_effort="low")
    captured: dict = {}

    mock_response = MagicMock()
    mock_response.content = []
    mock_response.usage = None
    mock_response.stop_reason = "end_turn"

    def fake_create(**kwargs):
        captured.update(kwargs)
        return mock_response

    mock_anthropic = MagicMock()
    mock_anthropic.messages.create.side_effect = fake_create

    with patch("anthropic.Anthropic", return_value=mock_anthropic):
        client._invoke_anthropic(
            system_prompt="sys",
            body="hello",
            tools=None,
            on_token=None,
            on_reasoning=None,
        )

    assert captured["thinking"] == {"type": "enabled", "budget_tokens": 4096}
    assert captured["temperature"] == 1
    assert captured["max_tokens"] == _THINKING_MAX_TOKENS_MAP["low"]


# -------------------------------------------------------------------
# NativeProviderClient — injection: streaming path
# -------------------------------------------------------------------

def test_thinking_effort_injects_thinking_block_streaming() -> None:
    client = _make_client(thinking_effort="medium")
    captured: dict = {}

    mock_stream = MagicMock()
    mock_stream.__enter__ = lambda s: s
    mock_stream.__exit__ = MagicMock(return_value=False)
    mock_stream.__iter__ = lambda s: iter([])
    mock_stream.get_final_message.return_value = MagicMock(
        content=[], usage=None, stop_reason="end_turn"
    )

    def fake_stream(**kwargs):
        captured.update(kwargs)
        return mock_stream

    mock_anthropic = MagicMock()
    mock_anthropic.messages.stream.side_effect = fake_stream

    tokens: list[str] = []
    with patch("anthropic.Anthropic", return_value=mock_anthropic):
        client._invoke_anthropic_chat(
            system_prompt="sys",
            messages=[{"role": "user", "content": "hi"}],
            tools=None,
            on_token=tokens.append,
            on_reasoning=None,
        )

    assert captured["thinking"] == {"type": "enabled", "budget_tokens": 8192}
    assert captured["temperature"] == 1
    assert captured["max_tokens"] == _THINKING_MAX_TOKENS_MAP["medium"]


# -------------------------------------------------------------------
# NativeProviderClient — OpenAI path unaffected
# -------------------------------------------------------------------

def test_openai_call_unaffected_by_thinking_effort() -> None:
    ep = ProviderEndpoint(
        provider="openai",
        model="gpt-4o",
        api_key="test-key",
        thinking_effort="high",  # should be ignored for OpenAI
    )
    client = NativeProviderClient(ep)
    captured: dict = {}

    mock_response = MagicMock()
    mock_response.choices = [MagicMock(
        message=MagicMock(content="ok", tool_calls=None),
        finish_reason="stop",
    )]
    mock_response.usage = None

    def fake_create(**kwargs):
        captured.update(kwargs)
        return mock_response

    mock_openai = MagicMock()
    mock_openai.chat.completions.create.side_effect = fake_create

    with patch("openai.OpenAI", return_value=mock_openai):
        client._invoke_openai_chat(
            system_prompt="sys",
            messages=[{"role": "user", "content": "hi"}],
            tools=None,
            on_token=None,
        )

    assert "thinking" not in captured
