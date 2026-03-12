from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import hmac
import time

from nacl.signing import SigningKey
from fastapi.testclient import TestClient
from slack_sdk.signature import SignatureVerifier

from teambot.channels.models import ChannelEnvelope
from teambot.channels.registry import list_channel_ids
from teambot.domain.models import OutboundReply, ReplyTarget
from teambot.gateway.dispatch import envelope_to_inbound_event
from teambot.app import main as app_main


class _FakeService:
    def __init__(self) -> None:
        self.events = []

    async def process_event(self, event):
        self.events.append(event)
        return OutboundReply(
            event_id=event.event_id,
            conversation_key=f"{event.team_id}:{event.channel_id}:{event.thread_ts}",
            reply_target=ReplyTarget(
                team_id=event.team_id,
                channel_id=event.channel_id,
                thread_ts=event.thread_ts,
            ),
            text=f"echo:{event.text}",
            skill_name="",
        )


def _signed_slack_headers(*, secret: str, body: str, timestamp: str | None = None) -> dict[str, str]:
    timestamp = timestamp or str(int(time.time()))
    verifier = SignatureVerifier(secret)
    signature = verifier.generate_signature(timestamp=timestamp, body=body)
    assert signature is not None
    return {
        "content-type": "application/json",
        "x-slack-request-timestamp": timestamp,
        "x-slack-signature": signature,
    }


def _signed_whatsapp_headers(*, secret: str, body: str) -> dict[str, str]:
    digest = hmac.new(secret.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).hexdigest()
    return {
        "content-type": "application/json",
        "x-hub-signature-256": f"sha256={digest}",
    }


def _signed_discord_headers(*, signing_key: SigningKey, body: str, timestamp: str | None = None) -> dict[str, str]:
    timestamp = timestamp or str(int(time.time()))
    signature = signing_key.sign(f"{timestamp}{body}".encode("utf-8")).signature.hex()
    return {
        "content-type": "application/json",
        "x-signature-timestamp": timestamp,
        "x-signature-ed25519": signature,
    }


def test_channel_registry_lists_supported_ingress_channels() -> None:
    assert list_channel_ids() == ["whatsapp", "slack", "telegram", "discord", "feishu"]


def test_envelope_maps_deterministically_to_existing_inbound_event() -> None:
    envelope = ChannelEnvelope(
        channel="telegram",
        event_type="message",
        event_id="evt-1",
        sender_id="user-1",
        conversation_id="chat-42",
        message_id="msg-7",
        thread_id="topic-9",
        text="hello",
        received_at=datetime(2026, 3, 11, 8, 0, tzinfo=timezone.utc),
        metadata={"workspace_id": "ws-1"},
        raw={"source": "test"},
    )

    inbound = envelope_to_inbound_event(envelope)

    assert inbound.event_id == "evt-1"
    assert inbound.event_type == "message"
    assert inbound.team_id == "ws-1"
    assert inbound.channel_id == "chat-42"
    assert inbound.thread_ts == "topic-9"
    assert inbound.user_id == "user-1"
    assert inbound.text == "hello"


def test_generic_gateway_route_dispatches_slack_payload(monkeypatch) -> None:
    fake_service = _FakeService()
    monkeypatch.setattr(app_main, "service", fake_service)

    client = TestClient(app_main.app)
    response = client.post(
        "/gateway/slack/events",
        json={
            "event_id": "evt-slack-1",
            "sender_id": "U1",
            "conversation_id": "C1",
            "thread_id": "1.1",
            "text": "hello from slack",
            "team_id": "T1",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ack"] is True
    assert body["dispatched"] == 1
    assert body["replies"][0]["text"] == "echo:hello from slack"
    assert fake_service.events[0].team_id == "T1"
    assert fake_service.events[0].channel_id == "C1"


def test_legacy_slack_route_uses_shared_gateway_dispatch(monkeypatch) -> None:
    fake_service = _FakeService()
    monkeypatch.setattr(app_main, "service", fake_service)

    client = TestClient(app_main.app)
    response = client.post(
        "/events/slack",
        json={
            "event_id": "evt-slack-legacy-1",
            "sender_id": "U2",
            "conversation_id": "C2",
            "thread_id": "2.1",
            "text": "legacy path",
            "team_id": "T2",
        },
    )

    assert response.status_code == 200
    assert response.json()["replies"][0]["text"] == "echo:legacy path"
    assert fake_service.events[0].event_id == "evt-slack-legacy-1"


def test_non_slack_channel_dispatches_via_same_gateway(monkeypatch) -> None:
    fake_service = _FakeService()
    monkeypatch.setattr(app_main, "service", fake_service)

    client = TestClient(app_main.app)
    response = client.post(
        "/gateway/telegram/events",
        json={
            "event_id": "evt-telegram-1",
            "sender_id": "tg-user-1",
            "conversation_id": "chat-1",
            "thread_id": "chat-1",
            "text": "hello telegram",
            "workspace_id": "telegram",
        },
    )

    assert response.status_code == 200
    assert response.json()["replies"][0]["text"] == "echo:hello telegram"
    assert fake_service.events[0].channel_id == "chat-1"


def test_legacy_generic_channel_route_uses_shared_gateway_dispatch(monkeypatch) -> None:
    fake_service = _FakeService()
    monkeypatch.setattr(app_main, "service", fake_service)

    client = TestClient(app_main.app)
    response = client.post(
        "/events/telegram",
        json={
            "event_id": "evt-telegram-legacy-1",
            "sender_id": "tg-user-legacy",
            "conversation_id": "chat-legacy-1",
            "thread_id": "chat-legacy-1",
            "text": "legacy telegram path",
            "workspace_id": "telegram",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ack"] is True
    assert body["channel"] == "telegram"
    assert body["dispatched"] == 1
    assert body["ignored"] == 0
    assert body["replies"][0]["text"] == "echo:legacy telegram path"
    assert fake_service.events[0].event_id == "evt-telegram-legacy-1"


def test_unknown_channel_returns_404(monkeypatch) -> None:
    monkeypatch.setattr(app_main, "service", _FakeService())

    client = TestClient(app_main.app)
    response = client.post("/gateway/unknown/events", json={"text": "hello"})

    assert response.status_code == 404


def test_invalid_payload_returns_422(monkeypatch) -> None:
    monkeypatch.setattr(app_main, "service", _FakeService())

    client = TestClient(app_main.app)
    response = client.post(
        "/gateway/feishu/events",
        json={
            "event_id": "evt-feishu-1",
            "sender_id": "ou_1",
            "conversation_id": "chat_1",
        },
    )

    assert response.status_code == 422


def test_slack_url_verification_returns_challenge_without_dispatch(monkeypatch) -> None:
    fake_service = _FakeService()
    monkeypatch.setattr(app_main, "service", fake_service)

    client = TestClient(app_main.app)
    response = client.post(
        "/gateway/slack/events",
        json={
            "type": "url_verification",
            "challenge": "slack-challenge-token",
        },
    )

    assert response.status_code == 200
    assert response.json() == {"challenge": "slack-challenge-token"}
    assert fake_service.events == []


def test_slack_signed_url_verification_requires_valid_signature_when_secret_is_configured(
    monkeypatch,
) -> None:
    fake_service = _FakeService()
    monkeypatch.setattr(app_main, "service", fake_service)
    monkeypatch.setenv("SLACK_SIGNING_SECRET", "slack-test-secret")

    body = '{"type":"url_verification","challenge":"signed-slack-challenge"}'
    headers = _signed_slack_headers(secret="slack-test-secret", body=body)

    client = TestClient(app_main.app)
    response = client.post("/gateway/slack/events", content=body, headers=headers)

    assert response.status_code == 200
    assert response.json() == {"challenge": "signed-slack-challenge"}
    assert fake_service.events == []


def test_slack_rejects_invalid_signature_when_secret_is_configured(monkeypatch) -> None:
    fake_service = _FakeService()
    monkeypatch.setattr(app_main, "service", fake_service)
    monkeypatch.setenv("SLACK_SIGNING_SECRET", "slack-test-secret")

    body = '{"type":"url_verification","challenge":"invalid-signed-slack-challenge"}'
    headers = {
        "content-type": "application/json",
        "x-slack-request-timestamp": "1710000000",
        "x-slack-signature": "v0=invalid",
    }

    client = TestClient(app_main.app)
    response = client.post("/gateway/slack/events", content=body, headers=headers)

    assert response.status_code == 401
    assert response.json()["detail"] == "invalid slack signature"
    assert fake_service.events == []


def test_slack_event_callback_message_normalizes_real_shape(monkeypatch) -> None:
    fake_service = _FakeService()
    monkeypatch.setattr(app_main, "service", fake_service)

    client = TestClient(app_main.app)
    response = client.post(
        "/gateway/slack/events",
        json={
            "type": "event_callback",
            "team_id": "T-slack",
            "event_id": "Ev123",
            "event": {
                "type": "message",
                "user": "U-slack",
                "channel": "C-slack",
                "ts": "171234.5678",
                "thread_ts": "171234.5678",
                "text": "hello from slack callback",
            },
        },
    )

    assert response.status_code == 200
    assert response.json()["replies"][0]["text"] == "echo:hello from slack callback"
    event = fake_service.events[0]
    assert event.event_id == "Ev123"
    assert event.team_id == "T-slack"
    assert event.channel_id == "C-slack"
    assert event.thread_ts == "171234.5678"
    assert event.user_id == "U-slack"


def test_feishu_url_verification_returns_challenge_without_dispatch(monkeypatch) -> None:
    fake_service = _FakeService()
    monkeypatch.setattr(app_main, "service", fake_service)

    client = TestClient(app_main.app)
    response = client.post(
        "/gateway/feishu/events",
        json={
            "type": "url_verification",
            "challenge": "feishu-challenge-token",
        },
    )

    assert response.status_code == 200
    assert response.json() == {"challenge": "feishu-challenge-token"}
    assert fake_service.events == []


def test_feishu_im_message_receive_event_normalizes_real_shape(monkeypatch) -> None:
    fake_service = _FakeService()
    monkeypatch.setattr(app_main, "service", fake_service)

    client = TestClient(app_main.app)
    response = client.post(
        "/gateway/feishu/events",
        json={
            "schema": "2.0",
            "header": {
                "event_type": "im.message.receive_v1",
                "event_id": "feishu-event-1",
                "tenant_key": "tenant-1",
            },
            "event": {
                "sender": {"sender_id": {"open_id": "ou_sender_1"}},
                "message": {
                    "message_id": "om_xxx",
                    "chat_id": "oc_xxx",
                    "chat_type": "group",
                    "message_type": "text",
                    "content": "{\"text\":\"hello from feishu\"}",
                    "create_time": "1712345678000",
                },
            },
        },
    )

    assert response.status_code == 200
    assert response.json()["replies"][0]["text"] == "echo:hello from feishu"
    event = fake_service.events[0]
    assert event.event_id == "feishu-event-1"
    assert event.team_id == "tenant-1"
    assert event.channel_id == "oc_xxx"
    assert event.thread_ts == "oc_xxx"
    assert event.user_id == "ou_sender_1"


def test_feishu_rejects_invalid_verification_token_when_configured(monkeypatch) -> None:
    fake_service = _FakeService()
    monkeypatch.setattr(app_main, "service", fake_service)
    monkeypatch.setenv("FEISHU_VERIFICATION_TOKEN", "expected-feishu-token")

    client = TestClient(app_main.app)
    response = client.post(
        "/gateway/feishu/events",
        json={
            "schema": "2.0",
            "header": {
                "event_type": "im.message.receive_v1",
                "event_id": "feishu-event-invalid-token",
                "tenant_key": "tenant-1",
                "token": "wrong-token",
            },
            "event": {
                "sender": {"sender_id": {"open_id": "ou_sender_1"}},
                "message": {
                    "message_id": "om_invalid",
                    "chat_id": "oc_invalid",
                    "chat_type": "group",
                    "message_type": "text",
                    "content": "{\"text\":\"hello from feishu invalid token\"}",
                    "create_time": "1712345678000",
                },
            },
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "invalid feishu request"
    assert fake_service.events == []


def test_telegram_message_update_normalizes_real_shape(monkeypatch) -> None:
    fake_service = _FakeService()
    monkeypatch.setattr(app_main, "service", fake_service)

    client = TestClient(app_main.app)
    response = client.post(
        "/gateway/telegram/events",
        json={
            "update_id": 987654321,
            "message": {
                "message_id": 12,
                "date": 1712345678,
                "text": "hello from telegram update",
                "from": {
                    "id": 123456,
                    "is_bot": False,
                    "first_name": "Nigel",
                },
                "chat": {
                    "id": -100222333444,
                    "type": "supergroup",
                    "title": "TeamBot Lab",
                },
                "message_thread_id": 77,
            },
        },
    )

    assert response.status_code == 200
    assert response.json()["replies"][0]["text"] == "echo:hello from telegram update"
    event = fake_service.events[0]
    assert event.event_id == "987654321"
    assert event.team_id == "telegram"
    assert event.channel_id == "-100222333444"
    assert event.thread_ts == "77"
    assert event.user_id == "123456"


def test_telegram_webhook_secret_token_allows_valid_signed_update(monkeypatch) -> None:
    fake_service = _FakeService()
    monkeypatch.setattr(app_main, "service", fake_service)
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET_TOKEN", "telegram-secret-token")

    client = TestClient(app_main.app)
    response = client.post(
        "/gateway/telegram/events",
        json={
            "update_id": 123456789,
            "message": {
                "message_id": 34,
                "date": 1712345678,
                "text": "hello from signed telegram update",
                "from": {
                    "id": 654321,
                    "is_bot": False,
                    "first_name": "Nigel",
                },
                "chat": {
                    "id": -100333444555,
                    "type": "supergroup",
                    "title": "TeamBot Signed Lab",
                },
            },
        },
        headers={"x-telegram-bot-api-secret-token": "telegram-secret-token"},
    )

    assert response.status_code == 200
    assert response.json()["replies"][0]["text"] == "echo:hello from signed telegram update"
    assert fake_service.events[0].event_id == "123456789"


def test_telegram_webhook_secret_token_rejects_invalid_header(monkeypatch) -> None:
    fake_service = _FakeService()
    monkeypatch.setattr(app_main, "service", fake_service)
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET_TOKEN", "telegram-secret-token")

    client = TestClient(app_main.app)
    response = client.post(
        "/gateway/telegram/events",
        json={
            "update_id": 123456790,
            "message": {
                "message_id": 35,
                "date": 1712345678,
                "text": "hello from invalid telegram update",
                "from": {
                    "id": 654321,
                    "is_bot": False,
                    "first_name": "Nigel",
                },
                "chat": {
                    "id": -100333444555,
                    "type": "supergroup",
                    "title": "TeamBot Signed Lab",
                },
            },
        },
        headers={"x-telegram-bot-api-secret-token": "wrong-token"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "invalid telegram webhook secret"
    assert fake_service.events == []


def test_whatsapp_webhook_message_normalizes_real_shape(monkeypatch) -> None:
    fake_service = _FakeService()
    monkeypatch.setattr(app_main, "service", fake_service)

    client = TestClient(app_main.app)
    response = client.post(
        "/gateway/whatsapp/events",
        json={
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "WABA-1",
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {
                                    "display_phone_number": "15550001111",
                                    "phone_number_id": "phone-number-1",
                                },
                                "contacts": [
                                    {
                                        "profile": {"name": "Nigel"},
                                        "wa_id": "6588889999",
                                    }
                                ],
                                "messages": [
                                    {
                                        "from": "6588889999",
                                        "id": "wamid.HBgLN",
                                        "timestamp": "1712345678",
                                        "text": {"body": "hello from whatsapp webhook"},
                                        "type": "text",
                                    }
                                ],
                            },
                        }
                    ],
                }
            ],
        },
    )

    assert response.status_code == 200
    assert response.json()["replies"][0]["text"] == "echo:hello from whatsapp webhook"
    event = fake_service.events[0]
    assert event.event_id == "wamid.HBgLN"
    assert event.team_id == "phone-number-1"
    assert event.channel_id == "6588889999"
    assert event.thread_ts == "6588889999"
    assert event.user_id == "6588889999"


def test_whatsapp_webhook_challenge_uses_verify_token_when_configured(monkeypatch) -> None:
    fake_service = _FakeService()
    monkeypatch.setattr(app_main, "service", fake_service)
    monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", "whatsapp-verify-token")

    client = TestClient(app_main.app)
    response = client.get(
        "/gateway/whatsapp/events",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "whatsapp-verify-token",
            "hub.challenge": "123456789",
        },
    )

    assert response.status_code == 200
    assert response.text == "123456789"
    assert fake_service.events == []


def test_whatsapp_rejects_invalid_signature_when_app_secret_is_configured(monkeypatch) -> None:
    fake_service = _FakeService()
    monkeypatch.setattr(app_main, "service", fake_service)
    monkeypatch.setenv("WHATSAPP_APP_SECRET", "whatsapp-app-secret")

    body = (
        '{"object":"whatsapp_business_account","entry":[{"id":"WABA-1","changes":[{"field":"messages",'
        '"value":{"messaging_product":"whatsapp","metadata":{"phone_number_id":"phone-number-1"},'
        '"messages":[{"from":"6588889999","id":"wamid.invalid","timestamp":"1712345678",'
        '"text":{"body":"hello invalid signature"},"type":"text"}]}}]}]}'
    )

    client = TestClient(app_main.app)
    response = client.post(
        "/gateway/whatsapp/events",
        content=body,
        headers={
            "content-type": "application/json",
            "x-hub-signature-256": "sha256=invalid",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "invalid whatsapp signature"
    assert fake_service.events == []


def test_discord_ping_interaction_returns_pong_without_dispatch(monkeypatch) -> None:
    fake_service = _FakeService()
    monkeypatch.setattr(app_main, "service", fake_service)

    client = TestClient(app_main.app)
    response = client.post(
        "/gateway/discord/events",
        json={
            "id": "100000000000000001",
            "application_id": "200000000000000001",
            "type": 1,
            "token": "discord-ping-token",
            "version": 1,
        },
    )

    assert response.status_code == 200
    assert response.json() == {"type": 1}
    assert fake_service.events == []


def test_discord_application_command_normalizes_real_shape(monkeypatch) -> None:
    fake_service = _FakeService()
    monkeypatch.setattr(app_main, "service", fake_service)

    client = TestClient(app_main.app)
    response = client.post(
        "/gateway/discord/events",
        json={
            "id": "100000000000000002",
            "application_id": "200000000000000001",
            "type": 2,
            "guild_id": "300000000000000001",
            "channel_id": "400000000000000001",
            "member": {
                "user": {
                    "id": "500000000000000001",
                    "username": "nigel",
                    "discriminator": "0001",
                    "public_flags": 0,
                }
                ,
                "nick": None,
                "roles": [],
                "joined_at": "2024-01-01T00:00:00.000000+00:00",
                "pending": False,
            },
            "token": "discord-command-token",
            "version": 1,
            "data": {
                "id": "600000000000000001",
                "name": "ask",
                "options": [
                    {
                        "name": "text",
                        "type": 3,
                        "value": "hello from discord interaction",
                    }
                ],
            },
        },
    )

    assert response.status_code == 200
    assert response.json()["replies"][0]["text"] == "echo:hello from discord interaction"
    event = fake_service.events[0]
    assert event.event_id == "100000000000000002"
    assert event.team_id == "300000000000000001"
    assert event.channel_id == "400000000000000001"
    assert event.thread_ts == "400000000000000001"
    assert event.user_id == "500000000000000001"


def test_discord_signed_ping_requires_valid_signature_when_public_key_is_configured(monkeypatch) -> None:
    fake_service = _FakeService()
    monkeypatch.setattr(app_main, "service", fake_service)
    signing_key = SigningKey.generate()
    monkeypatch.setenv("DISCORD_PUBLIC_KEY", signing_key.verify_key.encode().hex())

    body = '{"id":"100000000000000003","application_id":"200000000000000001","type":1,"token":"discord-ping-token","version":1}'
    headers = _signed_discord_headers(signing_key=signing_key, body=body)

    client = TestClient(app_main.app)
    response = client.post("/gateway/discord/events", content=body, headers=headers)

    assert response.status_code == 200
    assert response.json() == {"type": 1}
    assert fake_service.events == []


def test_discord_rejects_invalid_signature_when_public_key_is_configured(monkeypatch) -> None:
    fake_service = _FakeService()
    monkeypatch.setattr(app_main, "service", fake_service)
    signing_key = SigningKey.generate()
    monkeypatch.setenv("DISCORD_PUBLIC_KEY", signing_key.verify_key.encode().hex())

    body = '{"id":"100000000000000004","application_id":"200000000000000001","type":1,"token":"discord-ping-token","version":1}'

    client = TestClient(app_main.app)
    response = client.post(
        "/gateway/discord/events",
        content=body,
        headers={
            "content-type": "application/json",
            "x-signature-timestamp": str(int(time.time())),
            "x-signature-ed25519": "00" * 64,
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "invalid discord signature"
    assert fake_service.events == []


def test_non_message_payloads_are_ignored_without_dispatch_for_current_phase_2_channels(
    monkeypatch,
) -> None:
    cases = [
        (
            "slack",
            {
                "type": "event_callback",
                "event_id": "slack-ignore-1",
                "event": {"type": "reaction_added", "user": "U1"},
            },
        ),
        (
            "feishu",
            {
                "schema": "2.0",
                "header": {
                    "event_type": "im.chat.member.bot.added_v1",
                    "event_id": "feishu-ignore-1",
                },
                "event": {},
            },
        ),
        (
            "whatsapp",
            {
                "object": "whatsapp_business_account",
                "entry": [{"changes": [{"value": {"statuses": [{"id": "status-1"}]}}]}],
            },
        ),
        (
            "discord",
            {
                "id": "discord-ignore-1",
                "type": 3,
            },
        ),
    ]

    for channel, payload in cases:
        fake_service = _FakeService()
        monkeypatch.setattr(app_main, "service", fake_service)
        client = TestClient(app_main.app)

        response = client.post(f"/gateway/{channel}/events", json=payload)

        assert response.status_code == 200
        assert response.json() == {
            "ack": True,
            "channel": channel,
            "dispatched": 0,
            "ignored": 1,
            "replies": [],
        }
        assert fake_service.events == []


def test_gateway_channels_endpoint_is_not_exposed_in_phase_2(monkeypatch) -> None:
    monkeypatch.setattr(app_main, "service", _FakeService())

    client = TestClient(app_main.app)
    response = client.get("/gateway/channels")

    assert response.status_code == 404


def test_gateway_single_channel_endpoint_is_not_exposed_in_phase_2(monkeypatch) -> None:
    monkeypatch.setattr(app_main, "service", _FakeService())

    client = TestClient(app_main.app)
    response = client.get("/gateway/channels/slack")

    assert response.status_code == 404


def test_gateway_single_channel_endpoint_returns_404_for_unknown(monkeypatch) -> None:
    monkeypatch.setattr(app_main, "service", _FakeService())

    client = TestClient(app_main.app)
    response = client.get("/gateway/channels/not-a-channel")

    assert response.status_code == 404
