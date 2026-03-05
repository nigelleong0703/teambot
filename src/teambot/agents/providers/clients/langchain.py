from __future__ import annotations

import json
from typing import Any, Callable

from ..base import NormalizedResponse, ProviderEndpoint, ProviderInvocationError
from ..registry import (
    SUPPORTED_PROVIDERS,
    is_anthropic_provider,
    is_openai_compatible_provider,
    normalize_provider_name,
)


class LangChainProviderClient:
    def __init__(self, endpoint: ProviderEndpoint) -> None:
        self.endpoint = endpoint
        self._model = None

    def invoke(
        self,
        *,
        system_prompt: str,
        payload: dict[str, Any] | str,
        tools: list[dict[str, Any]] | None = None,
        on_token: Callable[[str], None] | None = None,
        on_reasoning: Callable[[str], None] | None = None,
    ) -> NormalizedResponse:
        model = self._get_model()
        if tools:
            model = self._bind_tools(model, tools)
        try:
            from langchain_core.messages import HumanMessage, SystemMessage
        except Exception as exc:
            raise ProviderInvocationError(
                "langchain_core is required for provider clients"
            ) from exc

        body = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=body),
        ]
        if on_token is None or tools:
            response = model.invoke(messages)
            return normalize_chat_response(response)

        text_parts: list[str] = []
        usage: dict[str, Any] = {}
        finish_reason = ""
        raw_chunks: list[Any] = []
        stream_error: Exception | None = None
        try:
            for chunk in model.stream(messages):
                raw_chunks.append(chunk)
                piece = _extract_chunk_text(chunk)
                if piece:
                    text_parts.append(piece)
                    on_token(piece)
                reasoning_piece = _extract_chunk_reasoning(chunk)
                if reasoning_piece and on_reasoning is not None:
                    on_reasoning(reasoning_piece)
                chunk_finish = _extract_finish_reason(chunk)
                if chunk_finish:
                    finish_reason = chunk_finish
                chunk_usage = _extract_usage(chunk)
                if chunk_usage:
                    usage.update(chunk_usage)
        except Exception as exc:
            stream_error = exc

        if stream_error is not None or not text_parts:
            try:
                response = model.invoke(messages)
            except Exception as exc:
                if stream_error is not None:
                    raise ProviderInvocationError(
                        f"stream invocation failed: {stream_error}; invoke fallback failed: {exc}"
                    ) from exc
                raise ProviderInvocationError(
                    f"invoke fallback failed: {exc}"
                ) from exc

            normalized = normalize_chat_response(response)
            if normalized.text:
                on_token(normalized.text)
            return normalized

        return NormalizedResponse(
            text="".join(text_parts),
            finish_reason=finish_reason,
            usage=usage,
            raw=raw_chunks,
        )

    def _bind_tools(self, model: Any, tools: list[dict[str, Any]]) -> Any:
        provider = normalize_provider_name(self.endpoint.provider)
        provider_tools = [_tool_spec_for_provider(provider, tool) for tool in tools]
        try:
            return model.bind_tools(provider_tools, tool_choice="auto")
        except TypeError:
            return model.bind_tools(provider_tools)

    def _get_model(self):
        if self._model is not None:
            return self._model

        provider = normalize_provider_name(self.endpoint.provider)
        if is_openai_compatible_provider(provider):
            self._model = self._build_openai_model()
            return self._model

        if is_anthropic_provider(provider):
            self._model = self._build_anthropic_model()
            return self._model

        raise ProviderInvocationError(
            f"unsupported provider type: {self.endpoint.provider}. "
            f"supported={', '.join(SUPPORTED_PROVIDERS)}"
        )

    def _build_openai_model(self):
        try:
            from langchain_openai import ChatOpenAI
        except Exception as exc:
            raise ProviderInvocationError(
                "langchain_openai is required for OpenAI-compatible providers"
            ) from exc
        kwargs: dict[str, Any] = {
            "model": self.endpoint.model,
            "temperature": self.endpoint.temperature,
            "timeout": self.endpoint.timeout_seconds,
        }
        if self.endpoint.api_key:
            kwargs["api_key"] = self.endpoint.api_key
        if self.endpoint.base_url:
            kwargs["base_url"] = self.endpoint.base_url
        return ChatOpenAI(**kwargs)

    def _build_anthropic_model(self):
        try:
            from langchain_anthropic import ChatAnthropic
        except Exception as exc:
            raise ProviderInvocationError(
                "langchain_anthropic is required for Anthropic provider"
            ) from exc
        kwargs = {
            "model": self.endpoint.model,
            "temperature": self.endpoint.temperature,
            "timeout": self.endpoint.timeout_seconds,
        }
        if self.endpoint.api_key:
            kwargs["api_key"] = self.endpoint.api_key
        if self.endpoint.base_url:
            kwargs["base_url"] = self.endpoint.base_url
        return ChatAnthropic(**kwargs)


def normalize_chat_response(response: Any) -> NormalizedResponse:
    content = getattr(response, "content", "")
    text = _content_to_text(content)
    finish_reason = ""
    usage: dict[str, Any] = {}
    tool_calls = _extract_tool_calls(response)

    response_metadata = getattr(response, "response_metadata", None)
    if isinstance(response_metadata, dict):
        finish_reason = str(response_metadata.get("finish_reason", "")).strip()

    usage_metadata = getattr(response, "usage_metadata", None)
    if isinstance(usage_metadata, dict):
        usage = dict(usage_metadata)

    return NormalizedResponse(
        text=text,
        tool_calls=tool_calls,
        finish_reason=finish_reason,
        usage=usage,
        raw=response,
    )


def _content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        chunks: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    chunks.append(text)
            elif isinstance(item, str):
                chunks.append(item)
        return "".join(chunks)
    return str(content)


def _extract_chunk_text(chunk: Any) -> str:
    content = getattr(chunk, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        pieces: list[str] = []
        for item in content:
            if isinstance(item, str):
                pieces.append(item)
                continue
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    pieces.append(text)
        return "".join(pieces)
    return ""


def _extract_chunk_reasoning(chunk: Any) -> str:
    content = getattr(chunk, "content", "")
    if isinstance(content, list):
        pieces: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            kind = str(item.get("type", "")).strip().lower()
            if kind != "thinking":
                continue
            thinking = item.get("thinking")
            if isinstance(thinking, str) and thinking:
                pieces.append(thinking)
                continue
            text = item.get("text")
            if isinstance(text, str) and text:
                pieces.append(text)
        return "".join(pieces)
    return ""


def _extract_finish_reason(chunk: Any) -> str:
    metadata = getattr(chunk, "response_metadata", {})
    if isinstance(metadata, dict):
        reason = metadata.get("finish_reason")
        if isinstance(reason, str):
            return reason
    return ""


def _extract_usage(chunk: Any) -> dict[str, Any]:
    usage = getattr(chunk, "usage_metadata", {})
    if isinstance(usage, dict):
        return usage
    metadata = getattr(chunk, "response_metadata", {})
    if isinstance(metadata, dict):
        alt = metadata.get("usage")
        if isinstance(alt, dict):
            return alt
    return {}


def _tool_spec_for_provider(provider: str, tool: dict[str, Any]) -> dict[str, Any]:
    name = str(tool.get("name", "")).strip()
    description = str(tool.get("description", "")).strip()
    input_schema = tool.get("input_schema")
    if not isinstance(input_schema, dict):
        input_schema = {"type": "object", "properties": {}}

    if is_anthropic_provider(provider):
        return {
            "name": name,
            "description": description,
            "input_schema": input_schema,
        }
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": input_schema,
        },
    }


def _extract_tool_calls(response: Any) -> list[dict[str, Any]]:
    raw = getattr(response, "tool_calls", None)
    parsed: list[dict[str, Any]] = []
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            call_id = str(item.get("id", "")).strip()
            args_raw = item.get("args", {})
            args = _coerce_tool_args(args_raw)
            if not name:
                continue
            parsed.append(
                {
                    "name": name,
                    "arguments": args,
                    "id": call_id,
                }
            )
    if parsed:
        return parsed

    content = getattr(response, "content", None)
    if isinstance(content, list):
        for item in content:
            if not isinstance(item, dict):
                continue
            kind = str(item.get("type", "")).strip().lower()
            if kind != "tool_use":
                continue
            name = str(item.get("name", "")).strip()
            if not name:
                continue
            parsed.append(
                {
                    "name": name,
                    "arguments": _coerce_tool_args(item.get("input", {})),
                    "id": str(item.get("id", "")).strip(),
                }
            )
    return parsed


def _coerce_tool_args(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return {}
        try:
            decoded = json.loads(stripped)
        except json.JSONDecodeError:
            return {}
        if isinstance(decoded, dict):
            return decoded
    return {}
