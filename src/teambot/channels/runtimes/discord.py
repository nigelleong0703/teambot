from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from discord_interactions import Interaction, InteractionType, verify_key
from fastapi import HTTPException, Request

from ...gateway.manager import GatewayManager
from ...gateway.models import GatewayDispatchResponse
from ..models import ChannelEnvelope
from ..plugins.generic import read_json_body


def _looks_like_discord_sdk_request(request: Request, body: bytes) -> bool:
    if request.headers.get("x-signature-ed25519") or request.headers.get("x-signature-timestamp"):
        return True

    try:
        payload = read_json_body(body)
    except ValueError:
        return False

    if not isinstance(payload, dict):
        return False
    return payload.get("type") is not None and payload.get("id") is not None


def _resolve_command_text(interaction: Interaction) -> str | None:
    data = getattr(interaction, "data", None)
    options = getattr(data, "options", None)
    if not options:
        return None
    for option in options:
        value = getattr(option, "value", None)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _build_envelope(interaction: Interaction, payload: dict[str, Any]) -> ChannelEnvelope | None:
    if interaction.type != InteractionType.APPLICATION_COMMAND:
        return None
    if interaction.user is None or interaction.channel_id is None:
        raise ValueError("discord interaction must include user and channel identifiers")

    text = _resolve_command_text(interaction)
    if text is None:
        return None

    guild_id = getattr(interaction, "guild_id", None)
    command_name = getattr(getattr(interaction, "data", None), "name", None)
    return ChannelEnvelope(
        channel="discord",
        event_type="message",
        event_id=str(interaction.id),
        sender_id=str(interaction.user.id),
        conversation_id=str(interaction.channel_id),
        message_id=str(interaction.id),
        thread_id=str(interaction.channel_id),
        text=text,
        received_at=datetime.now(timezone.utc),
        metadata={
            "guild_id": str(guild_id) if guild_id is not None else None,
            "interaction_name": command_name,
        },
        raw=payload,
    )


class DiscordInteractionRuntime:
    async def handle_request(
        self,
        *,
        request: Request,
        gateway_manager: GatewayManager,
        fallback: Any,
    ) -> GatewayDispatchResponse | dict[str, Any]:
        body = await request.body()
        if not _looks_like_discord_sdk_request(request, body):
            return await fallback()

        public_key = os.getenv("DISCORD_PUBLIC_KEY", "").strip()
        if public_key:
            signature = request.headers.get("x-signature-ed25519")
            timestamp = request.headers.get("x-signature-timestamp")
            if not signature or not timestamp or not verify_key(body, signature, timestamp, public_key):
                raise HTTPException(status_code=401, detail="invalid discord signature")

        payload = read_json_body(body)
        if not isinstance(payload, dict):
            raise HTTPException(status_code=422, detail="request payload must be a JSON object")

        interaction_type = payload.get("type")
        if interaction_type not in {1, 2}:
            return GatewayDispatchResponse(channel="discord", dispatched=0, ignored=1, replies=[])

        try:
            interaction = Interaction.from_json(payload)
        except Exception as exc:
            raise HTTPException(status_code=422, detail="invalid discord interaction payload") from exc

        if interaction.type == InteractionType.PING:
            return {"type": 1}

        envelope = _build_envelope(interaction, payload)
        if envelope is None:
            return GatewayDispatchResponse(channel="discord", dispatched=0, ignored=1, replies=[])

        return await gateway_manager.dispatch_envelopes(channel="discord", envelopes=[envelope])
