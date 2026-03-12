from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, Request
from lark_oapi import EventDispatcherHandler
from lark_oapi.api.im.v1 import P2ImMessageReceiveV1
from lark_oapi.core.model import RawRequest

from ...gateway.manager import GatewayManager
from ...gateway.models import GatewayDispatchResponse
from ..models import ChannelEnvelope
from ..plugins.generic import read_json_body


def _extract_feishu_text(content: str | None) -> str | None:
    if not content:
        return None
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    text = parsed.get("text")
    if text is None:
        return None
    normalized = str(text).strip()
    return normalized or None


def _looks_like_feishu_sdk_request(request: Request, body: bytes) -> bool:
    if (
        request.headers.get("x-lark-signature")
        or request.headers.get("x-lark-request-timestamp")
        or request.headers.get("x-lark-request-nonce")
    ):
        return True

    try:
        payload = read_json_body(body)
    except ValueError:
        return False

    if not isinstance(payload, dict):
        return False
    if payload.get("type") == "url_verification":
        return True
    header = payload.get("header")
    return isinstance(header, dict) and header.get("event_type") is not None


def _build_dispatcher(payload: dict[str, Any], envelopes: list[ChannelEnvelope]) -> EventDispatcherHandler:
    builder = EventDispatcherHandler.builder(
        os.getenv("FEISHU_ENCRYPT_KEY", "").strip(),
        os.getenv("FEISHU_VERIFICATION_TOKEN", "").strip(),
    )

    def handle_message(data: P2ImMessageReceiveV1) -> None:
        event = data.event
        header = data.header
        if event is None or header is None or event.sender is None or event.message is None:
            return

        sender_id_obj = event.sender.sender_id
        sender_id = None
        if sender_id_obj is not None:
            sender_id = sender_id_obj.open_id or sender_id_obj.user_id or sender_id_obj.union_id
        message = event.message
        text = _extract_feishu_text(message.content)
        if sender_id is None or message.chat_id is None or text is None:
            return

        envelopes.append(
            ChannelEnvelope(
                channel="feishu",
                event_type="message",
                event_id=header.event_id or "",
                sender_id=sender_id,
                conversation_id=message.chat_id,
                message_id=message.message_id,
                thread_id=message.thread_id or message.chat_id,
                text=text,
                received_at=datetime.now(timezone.utc),
                metadata={
                    "workspace_id": header.tenant_key,
                    "chat_type": message.chat_type,
                    "message_type": message.message_type,
                },
                raw=payload,
            )
        )

    return builder.register_p2_im_message_receive_v1(handle_message).build()


def _build_raw_request(request: Request, body: bytes) -> RawRequest:
    raw_request = RawRequest()
    raw_request.uri = str(request.url.path)
    raw_request.body = body
    raw_request.headers = {key: value for key, value in request.headers.items()}
    for header_name in ("X-Lark-Request-Timestamp", "X-Lark-Request-Nonce", "X-Lark-Signature", "X-Request-Id"):
        value = request.headers.get(header_name)
        if value is not None:
            raw_request.headers[header_name] = value
    return raw_request


class FeishuLarkRuntime:
    async def handle_request(
        self,
        *,
        request: Request,
        gateway_manager: GatewayManager,
        fallback: Any,
    ) -> GatewayDispatchResponse | dict[str, Any]:
        body = await request.body()
        if not _looks_like_feishu_sdk_request(request, body):
            return await fallback()

        payload = read_json_body(body)
        if not isinstance(payload, dict):
            raise HTTPException(status_code=422, detail="request payload must be a JSON object")

        if payload.get("type") != "url_verification":
            header = payload.get("header")
            event_type = header.get("event_type") if isinstance(header, dict) else None
            if event_type != "im.message.receive_v1":
                return GatewayDispatchResponse(channel="feishu", dispatched=0, ignored=1, replies=[])

        envelopes: list[ChannelEnvelope] = []
        response = _build_dispatcher(payload, envelopes).do(_build_raw_request(request, body))
        body_text = response.content.decode("utf-8") if response.content else ""

        if response.status_code == 500 and (
            "invalid verification_token" in body_text or "signature verification failed" in body_text
        ):
            raise HTTPException(status_code=401, detail="invalid feishu request")
        if response.status_code and response.status_code >= 400:
            raise HTTPException(status_code=422, detail=body_text or "invalid feishu event payload")

        if envelopes:
            return await gateway_manager.dispatch_envelopes(channel="feishu", envelopes=envelopes)

        if body_text.strip():
            return json.loads(body_text)

        return GatewayDispatchResponse(channel="feishu", dispatched=0, ignored=1, replies=[])
