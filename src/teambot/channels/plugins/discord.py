from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..models import ChannelEnvelope, RawChannelEvent
from .generic import GenericJsonMessageChannelAdapter, first_string


def _resolve_command_text(data: dict[str, Any]) -> str | None:
    options = data.get("options")
    if not isinstance(options, list):
        return None
    for option in options:
        if not isinstance(option, dict):
            continue
        value = option.get("value")
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


class DiscordChannelAdapter(GenericJsonMessageChannelAdapter):
    def __init__(self) -> None:
        super().__init__("discord")

    async def resolve_immediate_response(
        self,
        raw_event: RawChannelEvent,
    ) -> dict[str, Any] | None:
        payload = raw_event.payload
        if payload.get("type") == 1:
            return {"type": 1}
        return None

    async def normalize_event(self, raw_event: RawChannelEvent) -> ChannelEnvelope | None:
        payload = raw_event.payload
        if payload.get("type") == 2:
            data = payload.get("data")
            member = payload.get("member")
            if not isinstance(data, dict):
                raise ValueError("discord interaction must include data object")
            if not isinstance(member, dict):
                raise ValueError("discord interaction must include member object")
            user = member.get("user")
            if not isinstance(user, dict):
                raise ValueError("discord interaction member must include user object")
            text = _resolve_command_text(data)
            sender_id = first_string(user, "id")
            conversation_id = first_string(payload, "channel_id")
            if text is None:
                return None
            if sender_id is None:
                raise ValueError("discord interaction user id is required")
            if conversation_id is None:
                raise ValueError("discord interaction channel_id is required")
            return ChannelEnvelope(
                channel="discord",
                event_type="message",
                event_id=first_string(payload, "id") or "",
                sender_id=sender_id,
                conversation_id=conversation_id,
                message_id=first_string(payload, "id"),
                thread_id=conversation_id,
                text=text,
                received_at=datetime.now(timezone.utc),
                metadata={
                    "guild_id": first_string(payload, "guild_id"),
                    "interaction_name": first_string(data, "name"),
                },
                raw=payload,
            )
        return await super().normalize_event(raw_event)
