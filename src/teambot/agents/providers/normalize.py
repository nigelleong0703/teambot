from __future__ import annotations

import json
import re
from typing import Any

from .base import NormalizedResponse, ProviderInvocationError


def normalize_chat_response(response: Any) -> NormalizedResponse:
    content = getattr(response, "content", "")
    text = _content_to_text(content)
    finish_reason = ""
    usage: dict[str, Any] = {}

    response_metadata = getattr(response, "response_metadata", None)
    if isinstance(response_metadata, dict):
        finish_reason = str(response_metadata.get("finish_reason", "")).strip()

    usage_metadata = getattr(response, "usage_metadata", None)
    if isinstance(usage_metadata, dict):
        usage = dict(usage_metadata)

    return NormalizedResponse(
        text=text,
        finish_reason=finish_reason,
        usage=usage,
        raw=response,
    )


def extract_json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        raw = json.loads(cleaned)
    except json.JSONDecodeError:
        raw = _extract_embedded_json(cleaned)

    if not isinstance(raw, dict):
        raise ProviderInvocationError("model output JSON must be object")
    return raw


def _extract_embedded_json(cleaned: str) -> dict[str, Any]:
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end <= start:
        raise ProviderInvocationError("model output does not contain JSON object")
    candidate = cleaned[start : end + 1]
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise ProviderInvocationError("model output JSON parse failed") from exc
    if not isinstance(parsed, dict):
        raise ProviderInvocationError("model output JSON must be object")
    return parsed


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

