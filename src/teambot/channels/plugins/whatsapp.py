from __future__ import annotations

from datetime import datetime, timezone

from ..models import ChannelEnvelope, RawChannelEvent
from .generic import GenericJsonMessageChannelAdapter, first_string


class WhatsAppChannelAdapter(GenericJsonMessageChannelAdapter):
    def __init__(self) -> None:
        super().__init__("whatsapp")

    async def normalize_event(self, raw_event: RawChannelEvent) -> ChannelEnvelope | None:
        payload = raw_event.payload
        entries = payload.get("entry")
        if isinstance(entries, list) and entries:
            first_entry = entries[0]
            if isinstance(first_entry, dict):
                changes = first_entry.get("changes")
                if isinstance(changes, list) and changes:
                    first_change = changes[0]
                    if isinstance(first_change, dict):
                        value = first_change.get("value")
                        if isinstance(value, dict):
                            messages = value.get("messages")
                            if not isinstance(messages, list) or not messages:
                                return None
                            first_message = messages[0]
                            if not isinstance(first_message, dict):
                                raise ValueError("whatsapp messages[0] must be an object")
                            if first_string(first_message, "type") != "text":
                                return None
                            text_payload = first_message.get("text")
                            text = None
                            if isinstance(text_payload, dict):
                                text = first_string(text_payload, "body")
                            sender_id = first_string(first_message, "from")
                            message_id = first_string(first_message, "id")
                            if sender_id is None:
                                raise ValueError("whatsapp message sender is required")
                            if message_id is None:
                                raise ValueError("whatsapp message id is required")
                            if text is None:
                                raise ValueError("whatsapp text.body is required")
                            metadata = value.get("metadata")
                            phone_number_id = None
                            if isinstance(metadata, dict):
                                phone_number_id = first_string(metadata, "phone_number_id")
                            return ChannelEnvelope(
                                channel="whatsapp",
                                event_type="message",
                                event_id=message_id,
                                sender_id=sender_id,
                                conversation_id=sender_id,
                                message_id=message_id,
                                thread_id=sender_id,
                                text=text,
                                received_at=datetime.now(timezone.utc),
                                metadata={
                                    "workspace_id": phone_number_id or "whatsapp",
                                    "messaging_product": value.get("messaging_product"),
                                },
                                raw=payload,
                            )
        return await super().normalize_event(raw_event)
