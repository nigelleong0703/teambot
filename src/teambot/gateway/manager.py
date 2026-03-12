from __future__ import annotations

from typing import Any, Callable

from fastapi import HTTPException, Request

from ..channels.models import ChannelEnvelope
from ..channels.registry import get_channel_adapter
from .dispatch import envelope_to_inbound_event
from .models import GatewayDispatchResponse


class GatewayManager:
    def __init__(self, *, service_getter: Callable[[], Any]) -> None:
        self._service_getter = service_getter

    async def dispatch_envelope(self, envelope: ChannelEnvelope) -> dict[str, Any]:
        inbound_event = envelope_to_inbound_event(envelope)
        reply = await self._service_getter().process_event(inbound_event)
        return reply.model_dump()

    async def dispatch_envelopes(
        self,
        *,
        channel: str,
        envelopes: list[ChannelEnvelope],
    ) -> GatewayDispatchResponse:
        replies = [await self.dispatch_envelope(envelope) for envelope in envelopes]
        return GatewayDispatchResponse(
            channel=channel,
            dispatched=len(envelopes),
            ignored=0,
            replies=replies,
        )

    async def handle_http_request(
        self,
        *,
        channel: str,
        request: Request,
    ) -> GatewayDispatchResponse | dict[str, Any]:
        adapter = get_channel_adapter(channel)
        if adapter is None:
            raise HTTPException(status_code=404, detail=f"unknown channel: {channel}")

        body = await request.body()
        verification = await adapter.verify_request(request, body)
        if not verification.ok:
            raise HTTPException(
                status_code=verification.status_code,
                detail=verification.reason or "request verification failed",
            )

        try:
            raw_events = await adapter.parse_request(request, body)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        replies: list[dict[str, Any]] = []
        dispatched = 0
        ignored = 0
        service = self._service_getter()

        for raw_event in raw_events:
            immediate_response = await adapter.resolve_immediate_response(raw_event)
            if immediate_response is not None:
                return immediate_response
            try:
                envelope = await adapter.normalize_event(raw_event)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            if envelope is None:
                ignored += 1
                continue

            reply = await self.dispatch_envelope(envelope)
            replies.append(reply)
            dispatched += 1

        return GatewayDispatchResponse(
            channel=adapter.channel_id,
            dispatched=dispatched,
            ignored=ignored,
            replies=replies,
        )
