from __future__ import annotations

import sys
import types

from teambot.providers.base import ProviderEndpoint
from teambot.providers.clients.langchain import LangChainProviderClient


class _Message:
    def __init__(self, *, content: str) -> None:
        self.content = content


class _Chunk:
    def __init__(
        self,
        *,
        content: str = "",
        tool_calls: list[dict] | None = None,
        finish_reason: str = "",
    ) -> None:
        self.content = content
        self.tool_calls = list(tool_calls or [])
        self.response_metadata = {"finish_reason": finish_reason} if finish_reason else {}
        self.usage_metadata = {}

    def __add__(self, other: "_Chunk") -> "_Chunk":
        combined = _Chunk(
            content=f"{self.content}{other.content}",
            tool_calls=[*self.tool_calls, *other.tool_calls],
            finish_reason=other.response_metadata.get("finish_reason", "")
            or self.response_metadata.get("finish_reason", ""),
        )
        return combined


class _FakeModel:
    def __init__(self) -> None:
        self.bound_tools = None
        self.invoke_calls = 0
        self.stream_calls = 0

    def bind_tools(self, tools, tool_choice="auto"):
        self.bound_tools = (tools, tool_choice)
        return self

    def stream(self, messages):
        _ = messages
        self.stream_calls += 1
        yield _Chunk(
            tool_calls=[
                {
                    "name": "get_current_time",
                    "args": {"timezone": "Asia/Kuala_Lumpur"},
                    "id": "call_1",
                }
            ],
            finish_reason="tool_calls",
        )

    def invoke(self, messages):
        _ = messages
        self.invoke_calls += 1
        raise AssertionError("invoke() should not be used for streamed tool calls")


def test_langchain_client_streams_tool_calling_without_falling_back(monkeypatch) -> None:
    fake_messages = types.SimpleNamespace(HumanMessage=_Message, SystemMessage=_Message)
    monkeypatch.setitem(sys.modules, "langchain_core.messages", fake_messages)

    endpoint = ProviderEndpoint(provider="openai-compatible", model="gpt-test")
    client = LangChainProviderClient(endpoint)
    model = _FakeModel()
    monkeypatch.setattr(client, "_get_model", lambda: model)

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

    assert model.stream_calls == 1
    assert model.invoke_calls == 0
    assert response.tool_calls[0]["name"] == "get_current_time"
    assert response.tool_calls[0]["arguments"]["timezone"] == "Asia/Kuala_Lumpur"
    assert "".join(tokens) == ""
