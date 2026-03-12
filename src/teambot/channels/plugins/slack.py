from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..models import ChannelEnvelope, RawChannelEvent
from .generic import GenericJsonMessageChannelAdapter, first_string


class SlackChannelAdapter(GenericJsonMessageChannelAdapter):
    def __init__(self) -> None:
        super().__init__("slack")

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
        if payload.get("type") == "event_callback":
            event = payload.get("event")
            if not isinstance(event, dict):
                raise ValueError("slack event callback must include an event object")
            event_type = first_string(event, "type") or ""
            if event_type != "message":
                return None
            sender_id = first_string(event, "user")
            conversation_id = first_string(event, "channel")
            text = first_string(event, "text")
            if sender_id is None:
                raise ValueError("slack message event user is required")
            if conversation_id is None:
                raise ValueError("slack message event channel is required")
            if text is None:
                raise ValueError("slack message event text is required")
            thread_id = first_string(event, "thread_ts", "ts") or conversation_id
            return ChannelEnvelope(
                channel="slack",
                event_type="message",
                event_id=first_string(payload, "event_id") or first_string(event, "client_msg_id") or "",
                sender_id=sender_id,
                conversation_id=conversation_id,
                message_id=first_string(event, "client_msg_id") or first_string(event, "ts"),
                thread_id=thread_id,
                text=text,
                received_at=datetime.now(timezone.utc),
                metadata={
                    "team_id": payload.get("team_id"),
                    "channel": "slack",
                    "raw_event_type": event_type,
                },
                raw=payload,
            )
        return await super().normalize_event(raw_event)
