from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, Request, Response
from pywa import WhatsApp, filters

from ...gateway.manager import GatewayManager
from ...gateway.models import GatewayDispatchResponse
from ..models import ChannelEnvelope
from ..plugins.generic import first_string, read_json_body


def _looks_like_whatsapp_sdk_request(request: Request, body: bytes) -> bool:
    if request.headers.get("x-hub-signature-256"):
        return True
    if request.method == "GET" and request.query_params.get("hub.mode") == "subscribe":
        return True
    try:
        payload = read_json_body(body)
    except ValueError:
        return False
    return isinstance(payload, dict) and first_string(payload, "object") == "whatsapp_business_account"


class WhatsAppPywaRuntime:
    def _build_client(self, envelopes: list[ChannelEnvelope]) -> WhatsApp:
        wa = WhatsApp(
            phone_id=os.getenv("WHATSAPP_PHONE_NUMBER_ID") or None,
            token=os.getenv("WHATSAPP_ACCESS_TOKEN") or "teambot-whatsapp-local",
            server=None,
            verify_token=os.getenv("WHATSAPP_VERIFY_TOKEN") or "teambot-whatsapp-verify",
            app_secret=os.getenv("WHATSAPP_APP_SECRET") or None,
            validate_updates=bool(os.getenv("WHATSAPP_APP_SECRET")),
        )

        @wa.on_message(filters.text)
        def handle_message(_: WhatsApp, msg: Any) -> None:
            raw = getattr(msg, "raw", {}) or {}
            metadata = {}
            phone_number_id = (
                raw.get("entry", [{}])[0]
                .get("changes", [{}])[0]
                .get("value", {})
                .get("metadata", {})
                .get("phone_number_id")
            )
            if phone_number_id is not None:
                metadata["workspace_id"] = phone_number_id
            messaging_product = (
                raw.get("entry", [{}])[0].get("changes", [{}])[0].get("value", {}).get("messaging_product")
            )
            if messaging_product is not None:
                metadata["messaging_product"] = messaging_product

            envelopes.append(
                ChannelEnvelope(
                    channel="whatsapp",
                    event_type="message",
                    event_id=str(msg.id),
                    sender_id=str(msg.from_user.wa_id),
                    conversation_id=str(msg.from_user.wa_id),
                    message_id=str(msg.id),
                    thread_id=str(msg.from_user.wa_id),
                    text=str(msg.text),
                    received_at=datetime.now(timezone.utc),
                    metadata=metadata,
                    raw=raw,
                )
            )

        return wa

    async def handle_challenge(self, request: Request) -> Response:
        client = self._build_client([])
        content, status_code = client.webhook_challenge_handler(
            vt=request.query_params.get("hub.verify_token"),
            ch=request.query_params.get("hub.challenge"),
        )
        return Response(content=content, status_code=status_code, media_type="text/plain")

    async def handle_request(
        self,
        *,
        request: Request,
        gateway_manager: GatewayManager,
        fallback: Any,
    ) -> GatewayDispatchResponse | dict[str, Any]:
        body = await request.body()
        if not _looks_like_whatsapp_sdk_request(request, body):
            return await fallback()

        envelopes: list[ChannelEnvelope] = []
        client = self._build_client(envelopes)
        content, status_code = client.webhook_update_handler(
            update=body,
            hmac_header=request.headers.get("x-hub-signature-256"),
        )

        if content in {"Unmatching signature", "Error, missing signature"} or status_code == 401:
            raise HTTPException(status_code=401, detail="invalid whatsapp signature")

        if envelopes:
            return await gateway_manager.dispatch_envelopes(channel="whatsapp", envelopes=envelopes)

        return GatewayDispatchResponse(channel="whatsapp", dispatched=0, ignored=1, replies=[])
