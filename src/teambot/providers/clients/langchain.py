"""Compatibility shim — LangChain is no longer used.

The real implementation lives in native.py. This module re-exports
NativeProviderClient as LangChainProviderClient and keeps
normalize_chat_response for callers that rely on it.
"""
from __future__ import annotations

import json
from typing import Any

from ..base import NormalizedResponse
from .native import NativeProviderClient, _ThinkTagStripper, _strip_think_tags

# Backward-compat alias
LangChainProviderClient = NativeProviderClient


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


def _extract_tool_calls(response: Any) -> list[dict[str, Any]]:
    """Extract tool calls from a LangChain-style response object."""
    raw = getattr(response, "tool_calls", None)
    parsed: list[dict[str, Any]] = []
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            call_id = str(item.get("id", "")).strip()
            args = _coerce_tool_args(item.get("args", {}))
            if not name:
                continue
            parsed.append({"name": name, "arguments": args, "id": call_id})
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
            parsed.append({
                "name": name,
                "arguments": _coerce_tool_args(item.get("input", {})),
                "id": str(item.get("id", "")).strip(),
            })
    return parsed


def normalize_chat_response(response: Any) -> NormalizedResponse:
    """Normalize a duck-typed response object (LangChain-style) to NormalizedResponse.

    Works with any object that has ``content``, ``response_metadata``, and
    ``usage_metadata`` attributes — no LangChain import required.
    """
    content = getattr(response, "content", "")
    text = _strip_think_tags(_content_to_text(content))
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
