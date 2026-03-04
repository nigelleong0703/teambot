from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pytest

from teambot.agents.providers.contracts import (
    NormalizedResponse,
    ProviderEndpoint,
    ProviderInvocationError,
    ProviderRoleBinding,
    ProviderSettings,
)
from teambot.agents.providers.langchain_client import normalize_chat_response
from teambot.agents.providers.manager import (
    ProviderClientRegistry,
    ProviderManager,
    extract_json_object,
)


@dataclass
class _FakeClient:
    endpoint: ProviderEndpoint
    fail: bool = False
    response_text: str = '{"ok": true}'

    def invoke(
        self,
        *,
        system_prompt: str,
        payload: dict | str,
        on_token: Callable[[str], None] | None = None,
    ) -> NormalizedResponse:
        if self.fail:
            raise RuntimeError(f"failed:{self.endpoint.model}")
        if on_token is not None:
            on_token('{"ok": ')
            on_token("true}")
        return NormalizedResponse(
            text=self.response_text,
            finish_reason="stop",
            usage={"total_tokens": 10},
            raw={"system_prompt": system_prompt, "payload": payload},
        )


def test_provider_manager_role_binding_and_failover() -> None:
    endpoints = [
        ProviderEndpoint(provider="openai-compatible", model="agent-primary"),
        ProviderEndpoint(provider="openai-compatible", model="agent-fallback"),
    ]
    settings = ProviderSettings(
        role_bindings={
            "agent_model": ProviderRoleBinding(
                role="agent_model",
                endpoints=endpoints,
                max_attempts=2,
            )
        }
    )

    def _factory(endpoint: ProviderEndpoint):
        if endpoint.model == "agent-primary":
            return _FakeClient(endpoint=endpoint, fail=True)
        return _FakeClient(
            endpoint=endpoint,
            response_text='{"selected_skill": "general_reply"}',
        )

    manager = ProviderManager(
        settings=settings,
        client_registry=ProviderClientRegistry(client_factory=_factory),
    )
    result = manager.invoke_role_json(
        role="agent_model",
        system_prompt="route",
        payload={"message": "hi"},
    )

    assert result.provider == "openai-compatible"
    assert result.model == "agent-fallback"
    assert result.data["selected_skill"] == "general_reply"


def test_provider_manager_structured_attempt_errors() -> None:
    endpoints = [
        ProviderEndpoint(provider="openai-compatible", model="m1", base_url="https://a"),
        ProviderEndpoint(provider="anthropic", model="m2", base_url="https://b"),
    ]
    settings = ProviderSettings(
        role_bindings={
            "agent_model": ProviderRoleBinding(
                role="agent_model",
                endpoints=endpoints,
                max_attempts=2,
            )
        }
    )

    manager = ProviderManager(
        settings=settings,
        client_registry=ProviderClientRegistry(
            client_factory=lambda endpoint: _FakeClient(endpoint=endpoint, fail=True)
        ),
    )

    with pytest.raises(ProviderInvocationError) as exc_info:
        manager.invoke_role_json(
            role="agent_model",
            system_prompt="plan",
            payload={"message": "hi"},
        )

    err = exc_info.value
    assert len(err.attempts) == 2
    assert err.attempts[0].provider == "openai-compatible"
    assert err.attempts[1].provider == "anthropic"


def test_response_normalization_and_json_extraction() -> None:
    class _Resp:
        content = [{"text": "```json\n{\"ok\": true}\n```"}]
        response_metadata = {"finish_reason": "stop"}
        usage_metadata = {"input_tokens": 5, "output_tokens": 3}

    normalized = normalize_chat_response(_Resp())
    parsed = extract_json_object(normalized.text)

    assert normalized.finish_reason == "stop"
    assert normalized.usage["input_tokens"] == 5
    assert parsed == {"ok": True}


def test_provider_manager_stream_callback_and_events() -> None:
    endpoint = ProviderEndpoint(provider="anthropic", model="m-stream")
    settings = ProviderSettings(
        role_bindings={
            "agent_model": ProviderRoleBinding(
                role="agent_model",
                endpoints=[endpoint],
                max_attempts=1,
            )
        }
    )
    events: list[tuple[str, dict]] = []
    tokens: list[str] = []
    manager = ProviderManager(
        settings=settings,
        client_registry=ProviderClientRegistry(
            client_factory=lambda ep: _FakeClient(
                endpoint=ep,
                response_text='{"ok": true}',
            )
        ),
    )
    manager.set_event_listener(lambda name, payload: events.append((name, payload)))
    result = manager.invoke_role_json(
        role="agent_model",
        system_prompt="x",
        payload={"message": "y"},
        on_token=lambda t: tokens.append(t),
    )

    assert result.data == {"ok": True}
    assert "".join(tokens) == '{"ok": true}'
    event_names = [name for name, _ in events]
    assert "model_start" in event_names
    assert "model_token" in event_names
    assert "model_end" in event_names


def test_provider_manager_text_invocation() -> None:
    endpoint = ProviderEndpoint(provider="openai-compatible", model="text-model")
    settings = ProviderSettings(
        role_bindings={
            "agent_model": ProviderRoleBinding(
                role="agent_model",
                endpoints=[endpoint],
                max_attempts=1,
            )
        }
    )
    manager = ProviderManager(
        settings=settings,
        client_registry=ProviderClientRegistry(
            client_factory=lambda ep: _FakeClient(
                endpoint=ep,
                response_text="hello from text mode",
            )
        ),
    )

    result = manager.invoke_role_text(
        role="agent_model",
        system_prompt="sys",
        user_message="hi",
    )
    assert result.text == "hello from text mode"
    assert result.provider == "openai-compatible"
