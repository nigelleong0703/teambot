from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from ..models import ChannelEnvelope, RawChannelEvent
from .generic import GenericJsonMessageChannelAdapter, first_string


def _extract_feishu_text(content: str) -> str | None:
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    text = parsed.get("text")
    if text is None:
        return None
    normalized = str(text).strip()
    return normalized or None


class FeishuChannelAdapter(GenericJsonMessageChannelAdapter):
    def __init__(self) -> None:
        super().__init__("feishu")

    async def resolve_immediate_response(
        self,
        raw_event: RawChannelEvent,
    ) -> dict[str, Any] | None:
        payload = raw_event.payload
        if payload.get("type") == "url_verification" and payload.get("challenge") is not None:
            return {"challenge": str(payload["challenge"])}
        return None

    async def normalize_event(self, raw_event: RawChannelEvent) -> ChannelEnvelope | None:
        payload = raw_event.payload
        header = payload.get("header")
        event = payload.get("event")
        if isinstance(header, dict) and isinstance(event, dict):
            event_type = first_string(header, "event_type") or ""
            if event_type != "im.message.receive_v1":
                return None
            sender = event.get("sender")
            message = event.get("message")
            if not isinstance(sender, dict) or not isinstance(message, dict):
                raise ValueError("feishu message event must include sender and message objects")
            sender_id_obj = sender.get("sender_id")
            sender_id = None
            if isinstance(sender_id_obj, dict):
                sender_id = first_string(sender_id_obj, "open_id", "user_id", "union_id")
            conversation_id = first_string(message, "chat_id")
            content_raw = first_string(message, "content")
            text = _extract_feishu_text(content_raw or "")
            if sender_id is None:
                raise ValueError("feishu sender open_id is required")
            if conversation_id is None:
                raise ValueError("feishu chat_id is required")
            if text is None:
                raise ValueError("feishu text message content is required")
            return ChannelEnvelope(
                channel="feishu",
                event_type="message",
                event_id=first_string(header, "event_id") or "",
                sender_id=sender_id,
                conversation_id=conversation_id,
                message_id=first_string(message, "message_id"),
                thread_id=conversation_id,
                text=text,
                received_at=datetime.now(timezone.utc),
                metadata={
                    "workspace_id": first_string(header, "tenant_key"),
                    "chat_type": message.get("chat_type"),
                    "message_type": message.get("message_type"),
                },
                raw=payload,
            )
        return await super().normalize_event(raw_event)
