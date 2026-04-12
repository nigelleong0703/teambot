import pytest

from teambot.domain.models import InboundEvent
from teambot.agent.service import AgentService


@pytest.mark.asyncio
async def test_reply_target_is_hard_routed_and_stable() -> None:
    service = AgentService()

    event = InboundEvent(
        event_id="evt-1",
        event_type="message",
        team_id="T1",
        channel_id="C1",
        thread_ts="1710000000.0001",
        user_id="U1",
        text="hello",
    )
    reply1 = await service.process_event(event)

    assert reply1.reply_target.team_id == "T1"
    assert reply1.reply_target.channel_id == "C1"
    assert reply1.reply_target.thread_ts == "1710000000.0001"

    # same event_id returns idempotent result
    reply2 = await service.process_event(event)
    assert reply2.model_dump() == reply1.model_dump()


@pytest.mark.asyncio
async def test_process_event_exposes_reply_text(monkeypatch) -> None:
    service = AgentService()

    monkeypatch.setattr(
        service._agent,
        "run_loop",
        lambda **_kwargs: (
            "It is 2026-03-06 09:00:00 in Kuala Lumpur.",
            [],
            {"input_tokens": 10, "output_tokens": 5},
        ),
    )

    event = InboundEvent(
        event_id="evt-2",
        event_type="message",
        team_id="T1",
        channel_id="C1",
        thread_ts="1710000000.0002",
        user_id="U1",
        text="what time is it?",
    )

    reply = await service.process_event(event)

    assert reply.text == "It is 2026-03-06 09:00:00 in Kuala Lumpur."


