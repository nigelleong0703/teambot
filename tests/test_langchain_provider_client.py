from __future__ import annotations

import types

from teambot.providers.base import ProviderEndpoint
from teambot.providers.clients.langchain import normalize_chat_response
from teambot.providers.clients.native import NativeProviderClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_openai_chunk(content: str | None = None, finish_reason: str | None = None):
    delta = types.SimpleNamespace(content=content)
    choice = types.SimpleNamespace(delta=delta, finish_reason=finish_reason)
    return types.SimpleNamespace(choices=[choice], usage=None)


def _make_openai_tool_response(name: str, arguments: str, call_id: str = "call_1"):
    func = types.SimpleNamespace(name=name, arguments=arguments)
    tc = types.SimpleNamespace(id=call_id, function=func)
    message = types.SimpleNamespace(content=None, tool_calls=[tc])
    choice = types.SimpleNamespace(message=message, finish_reason="tool_calls")
    return types.SimpleNamespace(choices=[choice], usage=None)


# ---------------------------------------------------------------------------
# Tool calling — non-streaming path
# ---------------------------------------------------------------------------


def test_native_client_uses_non_streaming_for_tool_calls(monkeypatch) -> None:
    """When tools are provided the client must not stream, even with on_token."""
    create_calls: list[dict] = []

    class _FakeCompletions:
        def create(self, *, stream: bool = False, stream_options=None, **kwargs):
            create_calls.append({"stream": stream})
            return _make_openai_tool_response(
                name="get_current_time",
                arguments='{"timezone": "Asia/Kuala_Lumpur"}',
            )

    fake_client = types.SimpleNamespace(
        chat=types.SimpleNamespace(completions=_FakeCompletions())
    )

    endpoint = ProviderEndpoint(provider="openai-compatible", model="gpt-test")
    client = NativeProviderClient(endpoint)
    monkeypatch.setattr(client, "_get_openai_client", lambda: fake_client)

    tokens: list[str] = []
    response = client.invoke(
        system_prompt="sys",
        payload={"message": "time"},
        tools=[
            {
                "name": "get_current_time",
                "description": "Get current time",
                "input_schema": {"type": "object", "properties": {}},
            }
        ],
        on_token=tokens.append,
    )

    assert len(create_calls) == 1
    assert create_calls[0]["stream"] is False
    assert response.tool_calls[0]["name"] == "get_current_time"
    assert response.tool_calls[0]["arguments"]["timezone"] == "Asia/Kuala_Lumpur"
    assert "".join(tokens) == ""


# ---------------------------------------------------------------------------
# Streaming — think-tag stripping
# ---------------------------------------------------------------------------


def test_native_client_streaming_strips_think_blocks(monkeypatch) -> None:
    class _FakeCompletions:
        def create(self, *, stream: bool = False, stream_options=None, **kwargs):
            if stream:
                return iter([
                    _make_openai_chunk("<think>"),
                    _make_openai_chunk("hidden"),
                    _make_openai_chunk("</think>Hello"),
                    _make_openai_chunk(" world"),
                    # final empty choices chunk
                    types.SimpleNamespace(choices=[], usage=None),
                ])
            raise AssertionError("non-streaming fallback should not be called")

    fake_client = types.SimpleNamespace(
        chat=types.SimpleNamespace(completions=_FakeCompletions())
    )

    endpoint = ProviderEndpoint(provider="openai-compatible", model="gpt-test")
    client = NativeProviderClient(endpoint)
    monkeypatch.setattr(client, "_get_openai_client", lambda: fake_client)

    tokens: list[str] = []
    response = client.invoke(
        system_prompt="sys",
        payload={"message": "hi"},
        on_token=tokens.append,
    )

    assert "".join(tokens) == "Hello world"
    assert response.text == "Hello world"


# ---------------------------------------------------------------------------
# normalize_chat_response — duck-typed response objects
# ---------------------------------------------------------------------------


def test_normalize_chat_response_strips_inline_think_tags() -> None:
    class _Resp:
        content = "<think>internal reasoning</think>Hello there"
        response_metadata = {"finish_reason": "stop"}
        usage_metadata = {}

    normalized = normalize_chat_response(_Resp())

    assert normalized.text == "Hello there"


def test_normalize_chat_response_list_content() -> None:
    class _Resp:
        content = [{"text": "```json\n{\"ok\": true}\n```"}]
        response_metadata = {"finish_reason": "stop"}
        usage_metadata = {"input_tokens": 5, "output_tokens": 3}

    normalized = normalize_chat_response(_Resp())

    assert normalized.finish_reason == "stop"
    assert normalized.usage["input_tokens"] == 5
    assert "ok" in normalized.text
