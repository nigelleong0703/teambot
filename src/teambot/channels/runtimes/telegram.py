from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, Request
from telegram import Bot, Update
from telegram.ext import filters

from ...gateway.manager import GatewayManager
from ...gateway.models import GatewayDispatchResponse
from ..models import ChannelEnvelope
from ..plugins.generic import read_json_body


def _looks_like_telegram_sdk_request(request: Request, body: bytes) -> bool:
    if request.headers.get("x-telegram-bot-api-secret-token"):
        return True

    try:
        payload = read_json_body(body)
    except ValueError:
        return False

    if not isinstance(payload, dict) or payload.get("update_id") is None:
        return False

    update_kinds = (
        "message",
        "edited_message",
        "channel_post",
        "edited_channel_post",
        "business_message",
        "edited_business_message",
    )
    return any(isinstance(payload.get(key), dict) for key in update_kinds)


def _build_bot() -> Bot:
    return Bot(token=os.getenv("TELEGRAM_BOT_TOKEN") or "123456:TEAMBOT_LOCAL")


def _build_envelope(update: Update, payload: dict[str, Any]) -> ChannelEnvelope | None:
    if not filters.TEXT.check_update(update):
        return None

    message = update.effective_message
    if message is None or message.from_user is None or message.chat is None or message.text is None:
        return None

    thread_id = message.message_thread_id
    return ChannelEnvelope(
        channel="telegram",
        event_type="message",
        event_id=str(update.update_id),
        sender_id=str(message.from_user.id),
        conversation_id=str(message.chat.id),
        message_id=str(message.message_id),
        thread_id=str(thread_id) if thread_id is not None else str(message.chat.id),
        text=message.text,
        received_at=datetime.now(timezone.utc),
        metadata={
            "workspace_id": "telegram",
            "chat_type": message.chat.type,
        },
        raw=payload,
    )


class TelegramPtbRuntime:
    async def handle_request(
        self,
        *,
        request: Request,
        gateway_manager: GatewayManager,
        fallback: Any,
    ) -> GatewayDispatchResponse | dict[str, Any]:
        body = await request.body()
        if not _looks_like_telegram_sdk_request(request, body):
            return await fallback()

        secret_token = os.getenv("TELEGRAM_WEBHOOK_SECRET_TOKEN", "").strip()
        received_secret = request.headers.get("x-telegram-bot-api-secret-token", "")
        if secret_token and received_secret != secret_token:
            raise HTTPException(status_code=401, detail="invalid telegram webhook secret")

        payload = read_json_body(body)
        if not isinstance(payload, dict):
            raise HTTPException(status_code=422, detail="request payload must be a JSON object")

        try:
            update = Update.de_json(payload, _build_bot())
        except Exception as exc:
            raise HTTPException(status_code=422, detail="invalid telegram update payload") from exc

        envelope = _build_envelope(update, payload)
        if envelope is None:
            return GatewayDispatchResponse(channel="telegram", dispatched=0, ignored=1, replies=[])

        return await gateway_manager.dispatch_envelopes(channel="telegram", envelopes=[envelope])
