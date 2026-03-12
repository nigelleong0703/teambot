from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from fastapi import Request

from .models import ChannelEnvelope, RawChannelEvent


@dataclass(frozen=True)
class ChannelVerificationResult:
    ok: bool
    reason: str = ""
    status_code: int = 401


class ChannelAdapter(Protocol):
    channel_id: str

    async def verify_request(
        self,
        request: Request,
        body: bytes,
    ) -> ChannelVerificationResult:
        ...

    async def parse_request(
        self,
        request: Request,
        body: bytes,
    ) -> list[RawChannelEvent]:
        ...

    async def resolve_immediate_response(
        self,
        raw_event: RawChannelEvent,
    ) -> dict[str, object] | None:
        ...

    async def normalize_event(self, raw_event: RawChannelEvent) -> ChannelEnvelope | None:
        ...
