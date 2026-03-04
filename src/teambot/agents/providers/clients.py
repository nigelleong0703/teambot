from __future__ import annotations

import json
from typing import Any, Callable

from .base import NormalizedResponse, ProviderEndpoint, ProviderInvocationError
from .normalize import normalize_chat_response


class LangChainProviderClient:
    def __init__(self, endpoint: ProviderEndpoint) -> None:
        self.endpoint = endpoint
        self._model = None

    def invoke(
        self,
        *,
        system_prompt: str,
        payload: dict[str, Any] | str,
        on_token: Callable[[str], None] | None = None,
    ) -> NormalizedResponse:
        model = self._get_model()
        try:
            from langchain_core.messages import HumanMessage, SystemMessage
        except Exception as exc:
            raise ProviderInvocationError(
                "langchain_core is required for provider clients"
            ) from exc

        if isinstance(payload, str):
            body = payload
        else:
            body = json.dumps(payload, ensure_ascii=False)
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=body),
        ]
        if on_token is None:
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
                chunk_finish = _extract_finish_reason(chunk)
                if chunk_finish:
                    finish_reason = chunk_finish
                chunk_usage = _extract_usage(chunk)
                if chunk_usage:
                    usage.update(chunk_usage)
        except Exception as exc:
            stream_error = exc

        # Some providers/endpoints do not emit token chunks reliably.
        # Fall back to non-stream invoke so debug mode does not appear stuck.
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

    def _get_model(self):
        if self._model is not None:
            return self._model

        provider = self.endpoint.provider.strip().lower()
        if provider in {"openai", "openai-compatible", "openai_compatible"}:
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
            self._model = ChatOpenAI(**kwargs)
            return self._model

        if provider == "anthropic":
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
            self._model = ChatAnthropic(**kwargs)
            return self._model

        raise ProviderInvocationError(
            f"unsupported provider type: {self.endpoint.provider}"
        )


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
