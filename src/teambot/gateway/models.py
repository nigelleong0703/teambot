from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class GatewayDispatchResponse(BaseModel):
    ack: bool = True
    channel: str
    dispatched: int = 0
    ignored: int = 0
    replies: list[dict[str, Any]] = Field(default_factory=list)
