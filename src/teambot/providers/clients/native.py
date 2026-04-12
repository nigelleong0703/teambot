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

_ANTHROPIC_DEFAULT_MAX_TOKENS = 8192

_THINKING_BUDGET_MAP: dict[str, int] = {}
_THINKING_MAX_TOKENS_MAP: dict[str, int] = {}


class NativeProviderClient:
    """Provider client using the openai and anthropic SDKs directly."""

    def __init__(self, endpoint: ProviderEndpoint) -> None:
        self.endpoint = endpoint

    def invoke(
        self,
        *,
        system_prompt: str,
        payload: dict[str, Any] | str,
        tools: list[dict[str, Any]] | None = None,
        on_token: Callable[[str], None] | None = None,
        on_reasoning: Callable[[str], None] | None = None,
    ) -> NormalizedResponse:
        provider = normalize_provider_name(self.endpoint.provider)
        body = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)

        if is_openai_compatible_provider(provider):
            return self._invoke_openai(
                system_prompt=system_prompt,
                body=body,
                tools=tools,
                on_token=on_token,
            )
        if is_anthropic_provider(provider):
            return self._invoke_anthropic(
                system_prompt=system_prompt,
                body=body,
                tools=tools,
                on_token=on_token,
                on_reasoning=on_reasoning,
            )
        raise ProviderInvocationError(
            f"unsupported provider type: {self.endpoint.provider}. "
            f"supported={', '.join(SUPPORTED_PROVIDERS)}"
        )

    def invoke_chat(
        self,
        *,
        system_prompt: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        on_token: Callable[[str], None] | None = None,
        on_reasoning: Callable[[str], None] | None = None,
    ) -> NormalizedResponse:
        """Invoke with a pre-built messages list (multi-turn conversation).

        ``messages`` uses OpenAI format — the system prompt is passed separately.
        Tool results use role ``"tool"`` with a ``tool_call_id`` field; this method
        converts them to Anthropic format automatically when the provider requires it.
        """
        provider = normalize_provider_name(self.endpoint.provider)
        if is_openai_compatible_provider(provider):
            return self._invoke_openai_chat(
                system_prompt=system_prompt,
                messages=messages,
                tools=tools,
                on_token=on_token,
            )
        if is_anthropic_provider(provider):
            return self._invoke_anthropic_chat(
                system_prompt=system_prompt,
                messages=messages,
                tools=tools,
                on_token=on_token,
                on_reasoning=on_reasoning,
            )
        raise ProviderInvocationError(
            f"unsupported provider type: {self.endpoint.provider}. "
            f"supported={', '.join(SUPPORTED_PROVIDERS)}"
        )

    # ------------------------------------------------------------------
    # OpenAI-compatible
    # ------------------------------------------------------------------

    def _get_openai_client(self) -> Any:
        try:
            import openai
        except Exception as exc:
            raise ProviderInvocationError(
                "openai package is required for OpenAI-compatible providers"
            ) from exc
        kwargs: dict[str, Any] = {"timeout": float(self.endpoint.timeout_seconds)}
        if self.endpoint.api_key:
            kwargs["api_key"] = self.endpoint.api_key
        if self.endpoint.base_url:
            kwargs["base_url"] = self.endpoint.base_url
        return openai.OpenAI(**kwargs)

    def _invoke_openai(
        self,
        *,
        system_prompt: str,
        body: str,
        tools: list[dict[str, Any]] | None,
        on_token: Callable[[str], None] | None,
    ) -> NormalizedResponse:
        client = self._get_openai_client()
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": body},
        ]
        params: dict[str, Any] = {
            "model": self.endpoint.model,
            "messages": messages,
            "temperature": self.endpoint.temperature,
        }
        if tools:
            params["tools"] = [_openai_tool_spec(t) for t in tools]
            params["tool_choice"] = "auto"

        # Streaming only for text-only responses; tools use a single non-streaming call.
        if on_token is not None and not tools:
            return self._invoke_openai_stream(client, params, on_token)

        try:
            response = client.chat.completions.create(**params)
        except Exception as exc:
            raise ProviderInvocationError(f"OpenAI invocation failed: {exc}") from exc

        choice = response.choices[0]
        text = _strip_think_tags(choice.message.content or "")
        tool_calls = _extract_openai_tool_calls(getattr(choice.message, "tool_calls", None))
        return NormalizedResponse(
            text=text,
            tool_calls=tool_calls,
            finish_reason=str(choice.finish_reason or ""),
            usage=_openai_usage(getattr(response, "usage", None)),
            raw=response,
        )

    def _invoke_openai_chat(
        self,
        *,
        system_prompt: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        on_token: Callable[[str], None] | None,
    ) -> NormalizedResponse:
        client = self._get_openai_client()
        full_messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            *_to_openai_messages(messages),
        ]
        params: dict[str, Any] = {
            "model": self.endpoint.model,
            "messages": full_messages,
            "temperature": self.endpoint.temperature,
        }
        if tools:
            params["tools"] = [_openai_tool_spec(t) for t in tools]
            params["tool_choice"] = "auto"

        if on_token is not None and not tools:
            return self._invoke_openai_stream(client, params, on_token)

        try:
            response = client.chat.completions.create(**params)
        except Exception as exc:
            raise ProviderInvocationError(f"OpenAI invocation failed: {exc}") from exc

        choice = response.choices[0]
        text = _strip_think_tags(choice.message.content or "")
        tool_calls = _extract_openai_tool_calls(getattr(choice.message, "tool_calls", None))
        return NormalizedResponse(
            text=text,
            tool_calls=tool_calls,
            finish_reason=str(choice.finish_reason or ""),
            usage=_openai_usage(getattr(response, "usage", None)),
            raw=response,
        )

    def _invoke_openai_stream(
        self,
        client: Any,
        params: dict[str, Any],
        on_token: Callable[[str], None],
    ) -> NormalizedResponse:
        text_parts: list[str] = []
        sanitizer = _ThinkTagStripper()
        finish_reason = ""
        usage: dict[str, Any] = {}
        stream_error: Exception | None = None

        try:
            stream = client.chat.completions.create(
                **params, stream=True, stream_options={"include_usage": True}
            )
            for chunk in stream:
                if chunk.choices:
                    piece = chunk.choices[0].delta.content or ""
                    if piece:
                        visible = sanitizer.push(piece)
                        if visible:
                            text_parts.append(visible)
                            on_token(visible)
                    chunk_finish = chunk.choices[0].finish_reason
                    if chunk_finish:
                        finish_reason = chunk_finish
                if getattr(chunk, "usage", None):
                    usage = _openai_usage(chunk.usage)
        except Exception as exc:
            stream_error = exc

        trailing = sanitizer.finish()
        if trailing:
            text_parts.append(trailing)
            on_token(trailing)

        text = "".join(text_parts)
        if stream_error is not None or not text:
            try:
                response = client.chat.completions.create(**params)
            except Exception as exc:
                if stream_error is not None:
                    raise ProviderInvocationError(
                        f"stream failed: {stream_error}; fallback failed: {exc}"
                    ) from exc
                raise ProviderInvocationError(f"fallback invocation failed: {exc}") from exc
            choice = response.choices[0]
            fallback_text = _strip_think_tags(choice.message.content or "")
            if fallback_text and not text_parts:
                on_token(fallback_text)
            return NormalizedResponse(
                text=fallback_text,
                tool_calls=_extract_openai_tool_calls(getattr(choice.message, "tool_calls", None)),
                finish_reason=str(choice.finish_reason or ""),
                usage=_openai_usage(getattr(response, "usage", None)),
                raw=response,
            )

        return NormalizedResponse(
            text=text, tool_calls=[], finish_reason=finish_reason, usage=usage, raw=None
        )

    # ------------------------------------------------------------------
    # Anthropic
    # ------------------------------------------------------------------

    def _get_anthropic_client(self) -> Any:
        try:
            import anthropic
        except Exception as exc:
            raise ProviderInvocationError(
                "anthropic package is required for Anthropic provider"
            ) from exc
        kwargs: dict[str, Any] = {"timeout": float(self.endpoint.timeout_seconds)}
        if self.endpoint.api_key:
            kwargs["api_key"] = self.endpoint.api_key
        if self.endpoint.base_url:
            kwargs["base_url"] = self.endpoint.base_url
        return anthropic.Anthropic(**kwargs)

    def _invoke_anthropic(
        self,
        *,
        system_prompt: str,
        body: str,
        tools: list[dict[str, Any]] | None,
        on_token: Callable[[str], None] | None,
        on_reasoning: Callable[[str], None] | None,
    ) -> NormalizedResponse:
        client = self._get_anthropic_client()
        params: dict[str, Any] = {
            "model": self.endpoint.model,
            "system": system_prompt,
            "messages": [{"role": "user", "content": body}],
            "temperature": self.endpoint.temperature,
            "max_tokens": _ANTHROPIC_DEFAULT_MAX_TOKENS,
        }
        if tools:
            params["tools"] = [_anthropic_tool_spec(t) for t in tools]
            params["tool_choice"] = {"type": "auto"}

        if on_token is not None or on_reasoning is not None:
            return self._invoke_anthropic_stream(client, params, on_token, on_reasoning)

        try:
            response = client.messages.create(**params)
        except Exception as exc:
            raise ProviderInvocationError(f"Anthropic invocation failed: {exc}") from exc

        return _normalize_anthropic_response(response)

    def _invoke_anthropic_chat(
        self,
        *,
        system_prompt: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        on_token: Callable[[str], None] | None,
        on_reasoning: Callable[[str], None] | None,
    ) -> NormalizedResponse:
        client = self._get_anthropic_client()
        params: dict[str, Any] = {
            "model": self.endpoint.model,
            "system": system_prompt,
            "messages": _to_anthropic_messages(messages),
            "temperature": self.endpoint.temperature,
            "max_tokens": _ANTHROPIC_DEFAULT_MAX_TOKENS,
        }
        if tools:
            params["tools"] = [_anthropic_tool_spec(t) for t in tools]
            params["tool_choice"] = {"type": "auto"}

        if on_token is not None or on_reasoning is not None:
            return self._invoke_anthropic_stream(client, params, on_token, on_reasoning)

        try:
            response = client.messages.create(**params)
        except Exception as exc:
            raise ProviderInvocationError(f"Anthropic invocation failed: {exc}") from exc

        return _normalize_anthropic_response(response)

    def _invoke_anthropic_stream(
        self,
        client: Any,
        params: dict[str, Any],
        on_token: Callable[[str], None] | None,
        on_reasoning: Callable[[str], None] | None,
    ) -> NormalizedResponse:
        text_parts: list[str] = []
        sanitizer = _ThinkTagStripper()
        stream_error: Exception | None = None
        final_message: Any = None

        try:
            with client.messages.stream(**params) as stream:
                for event in stream:
                    event_type = getattr(event, "type", "")
                    if event_type != "content_block_delta":
                        continue
                    delta = getattr(event, "delta", None)
                    if delta is None:
                        continue
                    delta_type = getattr(delta, "type", "")
                    if delta_type == "text_delta":
                        piece = getattr(delta, "text", "")
                        if piece:
                            visible = sanitizer.push(piece)
                            if visible:
                                text_parts.append(visible)
                                if on_token:
                                    on_token(visible)
                    elif delta_type == "thinking_delta":
                        thinking = getattr(delta, "thinking", "")
                        if thinking and on_reasoning:
                            on_reasoning(thinking)
                trailing = sanitizer.finish()
                if trailing:
                    text_parts.append(trailing)
                    if on_token:
                        on_token(trailing)
                final_message = stream.get_final_message()
        except Exception as exc:
            stream_error = exc

        if stream_error is not None or final_message is None:
            try:
                response = client.messages.create(**params)
            except Exception as exc:
                if stream_error is not None:
                    raise ProviderInvocationError(
                        f"stream failed: {stream_error}; fallback failed: {exc}"
                    ) from exc
                raise ProviderInvocationError(f"fallback invocation failed: {exc}") from exc
            normalized = _normalize_anthropic_response(response)
            if normalized.text and not text_parts and on_token:
                on_token(normalized.text)
            return normalized

        return _normalize_anthropic_response(final_message)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


class _ThinkTagStripper:
    def __init__(self) -> None:
        self._in_think = False
        self._pending = ""

    def push(self, value: str) -> str:
        return self._consume(value, final=False)

    def finish(self) -> str:
        return self._consume("", final=True)

    def _consume(self, value: str, *, final: bool) -> str:
        self._pending += value
        output: list[str] = []
        while self._pending:
            if self._in_think:
                close_index = self._pending.find("</think>")
                if close_index < 0:
                    if final:
                        self._pending = ""
                    else:
                        self._pending = self._pending[-7:]
                    return "".join(output)
                self._pending = self._pending[close_index + len("</think>"):]
                self._in_think = False
                continue

            open_index = self._pending.find("<think>")
            if open_index < 0:
                if final:
                    output.append(self._pending)
                    self._pending = ""
                elif len(self._pending) > 6:
                    output.append(self._pending[:-6])
                    self._pending = self._pending[-6:]
                return "".join(output)

            if open_index > 0:
                output.append(self._pending[:open_index])
            self._pending = self._pending[open_index + len("<think>"):]
            self._in_think = True
        return "".join(output)


def _strip_think_tags(value: str) -> str:
    if "<think>" not in value:
        return value
    stripper = _ThinkTagStripper()
    visible = stripper.push(value)
    visible += stripper.finish()
    return visible


def _openai_tool_spec(tool: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": str(tool.get("name", "")),
            "description": str(tool.get("description", "")),
            "parameters": tool.get("input_schema") or {"type": "object", "properties": {}},
        },
    }


def _anthropic_tool_spec(tool: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": str(tool.get("name", "")),
        "description": str(tool.get("description", "")),
        "input_schema": tool.get("input_schema") or {"type": "object", "properties": {}},
    }


def _extract_openai_tool_calls(tool_calls: Any) -> list[dict[str, Any]]:
    if not tool_calls:
        return []
    result = []
    for tc in tool_calls:
        func = getattr(tc, "function", None)
        if func is None:
            continue
        name = str(getattr(func, "name", "") or "")
        if not name:
            continue
        args_raw = getattr(func, "arguments", "") or ""
        args: dict[str, Any] = {}
        if args_raw:
            try:
                decoded = json.loads(args_raw)
                if isinstance(decoded, dict):
                    args = decoded
            except json.JSONDecodeError:
                pass
        result.append({"name": name, "arguments": args, "id": str(getattr(tc, "id", "") or "")})
    return result


def _normalize_anthropic_response(response: Any) -> NormalizedResponse:
    text_parts: list[str] = []
    tool_calls: list[dict[str, Any]] = []

    for block in getattr(response, "content", []):
        block_type = getattr(block, "type", "")
        if block_type == "text":
            text_parts.append(getattr(block, "text", ""))
        elif block_type == "tool_use":
            name = str(getattr(block, "name", "") or "")
            if name:
                tool_calls.append({
                    "name": name,
                    "arguments": getattr(block, "input", {}) or {},
                    "id": str(getattr(block, "id", "") or ""),
                })

    text = _strip_think_tags("".join(text_parts))
    usage_obj = getattr(response, "usage", None)
    usage: dict[str, Any] = {}
    if usage_obj is not None:
        usage = {
            "input_tokens": getattr(usage_obj, "input_tokens", 0),
            "output_tokens": getattr(usage_obj, "output_tokens", 0),
        }
    finish_reason = str(getattr(response, "stop_reason", "") or "")

    return NormalizedResponse(
        text=text,
        tool_calls=tool_calls,
        finish_reason=finish_reason,
        usage=usage,
        raw=response,
    )


def _to_openai_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalise internal messages to the OpenAI wire format.

    Converts assistant tool_calls from our internal representation
    ``{"id": ..., "name": ..., "arguments": dict}`` to the OpenAI format
    ``{"id": ..., "type": "function", "function": {"name": ..., "arguments": str}}``.
    All other message types are passed through unchanged.
    """
    result: list[dict[str, Any]] = []
    for msg in messages:
        role = msg.get("role", "")
        if role == "assistant" and msg.get("tool_calls"):
            openai_tool_calls = []
            for tc in msg["tool_calls"]:
                args = tc.get("arguments", {})
                args_str = json.dumps(args, ensure_ascii=False) if isinstance(args, dict) else str(args)
                openai_tool_calls.append({
                    "id": str(tc.get("id", "")),
                    "type": "function",
                    "function": {
                        "name": str(tc.get("name", "")),
                        "arguments": args_str,
                    },
                })
            result.append({
                "role": "assistant",
                "content": msg.get("content") or None,
                "tool_calls": openai_tool_calls,
            })
        else:
            result.append(msg)
    return result


def _to_anthropic_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert OpenAI-format messages to Anthropic format.

    Key differences:
    - Tool results (role ``"tool"``) become ``{"type": "tool_result"}`` blocks
      inside a ``role: "user"`` message.
    - Assistant tool calls become ``{"type": "tool_use"}`` content blocks.
    - Multiple consecutive tool results are batched into one user message.
    """
    result: list[dict[str, Any]] = []
    pending_tool_results: list[dict[str, Any]] = []

    def _flush_tool_results() -> None:
        if pending_tool_results:
            result.append({"role": "user", "content": list(pending_tool_results)})
            pending_tool_results.clear()

    for msg in messages:
        role = msg.get("role", "")

        if role == "tool":
            pending_tool_results.append({
                "type": "tool_result",
                "tool_use_id": str(msg.get("tool_call_id", "")),
                "content": str(msg.get("content", "")),
            })
            continue

        _flush_tool_results()

        if role == "user":
            result.append({"role": "user", "content": msg.get("content", "")})

        elif role == "assistant":
            tool_calls = msg.get("tool_calls") or []
            text = str(msg.get("content", "") or "")
            if tool_calls:
                content_blocks: list[dict[str, Any]] = []
                if text:
                    content_blocks.append({"type": "text", "text": text})
                for tc in tool_calls:
                    content_blocks.append({
                        "type": "tool_use",
                        "id": str(tc.get("id", "")),
                        "name": str(tc.get("name", "")),
                        "input": tc.get("arguments", {}),
                    })
                result.append({"role": "assistant", "content": content_blocks})
            else:
                result.append({"role": "assistant", "content": text})

    _flush_tool_results()
    return result


def _openai_usage(usage: Any) -> dict[str, Any]:
    if usage is None:
        return {}
    return {
        "input_tokens": getattr(usage, "prompt_tokens", 0),
        "output_tokens": getattr(usage, "completion_tokens", 0),
        "total_tokens": getattr(usage, "total_tokens", 0),
    }
