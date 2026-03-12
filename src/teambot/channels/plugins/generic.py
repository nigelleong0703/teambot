from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import Request

from ..base import ChannelVerificationResult
from ..models import ChannelEnvelope, ChannelId, RawChannelEvent


def read_json_body(body: bytes) -> Any:
    try:
        decoded = body.decode("utf-8") if body else "{}"
    except UnicodeDecodeError as exc:
        raise ValueError("request body must be utf-8 JSON") from exc
    try:
        return json.loads(decoded)
    except json.JSONDecodeError as exc:
        raise ValueError("request body must be valid JSON") from exc


def first_string(payload: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = payload.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


class GenericJsonMessageChannelAdapter:
    def __init__(self, channel_id: ChannelId) -> None:
        self.channel_id = channel_id

    async def verify_request(
        self,
        request: Request,
        body: bytes,
    ) -> ChannelVerificationResult:
        del request, body
        return ChannelVerificationResult(ok=True, status_code=200)

    async def parse_request(
        self,
        request: Request,
        body: bytes,
    ) -> list[RawChannelEvent]:
        payload = read_json_body(body)
        headers = {key.lower(): value for key, value in request.headers.items()}
        if isinstance(payload, dict):
            if isinstance(payload.get("events"), list):
                return [
                    RawChannelEvent(
                        channel=self.channel_id,
                        headers=headers,
                        body=body.decode("utf-8", errors="replace"),
                        payload=item,
                    )
                    for item in payload["events"]
                    if isinstance(item, dict)
                ]
            return [
                RawChannelEvent(
                    channel=self.channel_id,
                    headers=headers,
                    body=body.decode("utf-8", errors="replace"),
                    payload=payload,
                )
            ]
        raise ValueError("request payload must be a JSON object")

    async def resolve_immediate_response(
        self,
        raw_event: RawChannelEvent,
    ) -> dict[str, Any] | None:
        del raw_event
        return None

    async def normalize_event(self, raw_event: RawChannelEvent) -> ChannelEnvelope | None:
        payload = raw_event.payload
        event_type = first_string(payload, "event_type", "type") or "message"
        if event_type != "message":
            return None

        sender_id = first_string(payload, "sender_id", "user_id", "from_id", "author_id")
        if sender_id is None:
            raise ValueError("sender_id is required")

        conversation_id = first_string(
            payload,
            "conversation_id",
            "channel_id",
            "chat_id",
            "room_id",
            "thread_id",
        )
        if conversation_id is None:
            raise ValueError("conversation_id is required")

        text = first_string(payload, "text", "message", "content")
        if text is None:
            raise ValueError("text is required for message events")

        event_id = first_string(payload, "event_id", "message_event_id", "update_id") or str(
            uuid4()
        )
        message_id = first_string(payload, "message_id", "msg_id")
        thread_id = first_string(payload, "thread_id", "thread_ts", "topic_id") or conversation_id
        account_id = first_string(payload, "account_id")

        metadata: dict[str, Any] = {}
        for source_key, target_key in (
            ("team_id", "team_id"),
            ("workspace_id", "workspace_id"),
            ("guild_id", "guild_id"),
            ("chat_type", "chat_type"),
            ("reply_to_message_id", "reply_to_message_id"),
        ):
            if payload.get(source_key) is not None:
                metadata[target_key] = payload.get(source_key)

        if isinstance(payload.get("mentions"), list):
            metadata["mentions"] = payload.get("mentions")

        return ChannelEnvelope(
            channel=self.channel_id,
            event_type=event_type,
            event_id=event_id,
            account_id=account_id,
            sender_id=sender_id,
            conversation_id=conversation_id,
            message_id=message_id,
            thread_id=thread_id,
            text=text,
            received_at=datetime.now(timezone.utc),
            metadata=metadata,
            raw=payload,
        )
