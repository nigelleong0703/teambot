from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


ChannelId = Literal["whatsapp", "slack", "telegram", "discord", "feishu"]


class RawChannelEvent(BaseModel):
    channel: ChannelId
    headers: dict[str, str] = Field(default_factory=dict)
    body: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)


class ChannelEnvelope(BaseModel):
    channel: ChannelId
    event_type: str
    event_id: str
    account_id: str | None = None
    sender_id: str
    conversation_id: str
    message_id: str | None = None
    thread_id: str | None = None
    text: str = ""
    received_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)
    raw: dict[str, Any] = Field(default_factory=dict)
