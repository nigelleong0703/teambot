from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, Request
from slack_bolt.adapter.fastapi.async_handler import AsyncSlackRequestHandler
from slack_bolt.app.async_app import AsyncApp
from slack_bolt.authorization import AuthorizeResult

from ...gateway.manager import GatewayManager
from ...gateway.models import GatewayDispatchResponse
from ..models import ChannelEnvelope
from ..plugins.generic import first_string, read_json_body


def _build_slack_message_envelope(*, event: dict[str, Any], body: dict[str, Any]) -> ChannelEnvelope | None:
    event_type = first_string(event, "type") or ""
    if event_type != "message":
        return None

    sender_id = first_string(event, "user")
    conversation_id = first_string(event, "channel")
    text = first_string(event, "text")
    if sender_id is None:
        raise ValueError("slack message event user is required")
    if conversation_id is None:
        raise ValueError("slack message event channel is required")
    if text is None:
        raise ValueError("slack message event text is required")

    thread_id = first_string(event, "thread_ts", "ts") or conversation_id
    return ChannelEnvelope(
        channel="slack",
        event_type="message",
        event_id=first_string(body, "event_id") or first_string(event, "client_msg_id") or "",
        sender_id=sender_id,
        conversation_id=conversation_id,
        message_id=first_string(event, "client_msg_id") or first_string(event, "ts"),
        thread_id=thread_id,
        text=text,
        received_at=datetime.now(timezone.utc),
        metadata={
            "team_id": body.get("team_id"),
            "channel": "slack",
            "raw_event_type": event_type,
        },
        raw=body,
    )


def _looks_like_slack_sdk_request(request: Request, body: bytes) -> bool:
    if request.headers.get("x-slack-signature") or request.headers.get("x-slack-request-timestamp"):
        return True

    try:
        payload = read_json_body(body)
    except ValueError:
        return False

    if not isinstance(payload, dict):
        return False
    payload_type = first_string(payload, "type")
    return payload_type in {"url_verification", "event_callback"}


class SlackBoltRuntime:
    def __init__(self) -> None:
        pass

    @staticmethod
    async def _authorize(**kwargs: Any) -> AuthorizeResult:
        context = kwargs.get("context")
        team_id = getattr(context, "team_id", None)
        return AuthorizeResult(
            enterprise_id=None,
            team_id=team_id,
            bot_user_id="Uteambot",
            bot_id="Bteambot",
            bot_token=os.getenv("SLACK_BOT_TOKEN") or "xoxb-teambot-local",
        )

    def _build_app(self) -> AsyncApp:
        signing_secret = os.getenv("SLACK_SIGNING_SECRET", "").strip() or "unused-signing-secret"
        app = AsyncApp(
            signing_secret=signing_secret,
            authorize=self._authorize,
            request_verification_enabled=bool(os.getenv("SLACK_SIGNING_SECRET", "").strip()),
            ignoring_self_events_enabled=False,
            process_before_response=True,
            raise_error_for_unhandled_request=False,
        )

        @app.event("message")
        async def handle_message(event: dict[str, Any], body: dict[str, Any], context: dict[str, Any]) -> None:
            envelope = _build_slack_message_envelope(event=event, body=body)
            if envelope is None:
                return
            context.setdefault("teambot_envelopes", []).append(envelope)

        return app

    def _build_handler(self) -> AsyncSlackRequestHandler:
        return AsyncSlackRequestHandler(self._build_app())

    async def handle_request(
        self,
        *,
        request: Request,
        gateway_manager: GatewayManager,
        fallback: Any,
    ) -> GatewayDispatchResponse | dict[str, Any]:
        body = await request.body()
        if not _looks_like_slack_sdk_request(request, body):
            return await fallback()

        payload = read_json_body(body)
        if isinstance(payload, dict) and first_string(payload, "type") == "event_callback":
            event = payload.get("event")
            if isinstance(event, dict) and first_string(event, "type") != "message":
                return GatewayDispatchResponse(channel="slack", dispatched=0, ignored=1, replies=[])

        envelopes: list[ChannelEnvelope] = []
        response = await self._build_handler().handle(
            request,
            {"teambot_envelopes": envelopes},
        )

        if response.status_code in {401, 403}:
            raise HTTPException(status_code=401, detail="invalid slack signature")

        if envelopes:
            return await gateway_manager.dispatch_envelopes(channel="slack", envelopes=envelopes)

        body_text = response.body.decode("utf-8") if isinstance(response.body, bytes) else str(response.body)
        if body_text.strip():
            try:
                return json.loads(body_text)
            except json.JSONDecodeError:
                return {"ack": response.status_code == 200, "channel": "slack", "body": body_text}

        return GatewayDispatchResponse(channel="slack", dispatched=0, ignored=1, replies=[])
