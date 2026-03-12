from __future__ import annotations

from datetime import datetime, timezone

from ..models import ChannelEnvelope, RawChannelEvent
from .generic import GenericJsonMessageChannelAdapter, first_string


class TelegramChannelAdapter(GenericJsonMessageChannelAdapter):
    def __init__(self) -> None:
        super().__init__("telegram")

    async def normalize_event(self, raw_event: RawChannelEvent) -> ChannelEnvelope | None:
        payload = raw_event.payload
        message = payload.get("message")
        if isinstance(message, dict):
            text = first_string(message, "text")
            if text is None:
                return None
            sender = message.get("from")
            chat = message.get("chat")
            if not isinstance(sender, dict) or not isinstance(chat, dict):
                raise ValueError("telegram message update must include from and chat objects")
            sender_id = first_string(sender, "id")
            conversation_id = first_string(chat, "id")
            if sender_id is None:
                raise ValueError("telegram sender id is required")
            if conversation_id is None:
                raise ValueError("telegram chat id is required")
            return ChannelEnvelope(
                channel="telegram",
                event_type="message",
                event_id=first_string(payload, "update_id") or first_string(message, "message_id") or "",
                sender_id=sender_id,
                conversation_id=conversation_id,
                message_id=first_string(message, "message_id"),
                thread_id=first_string(message, "message_thread_id") or conversation_id,
                text=text,
                received_at=datetime.now(timezone.utc),
                metadata={
                    "workspace_id": "telegram",
                    "chat_type": chat.get("type"),
                },
                raw=payload,
            )
        return await super().normalize_event(raw_event)
