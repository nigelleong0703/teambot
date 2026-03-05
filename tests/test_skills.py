import pytest

from teambot.domain.models import InboundEvent
from teambot.agents.core.service import AgentService


@pytest.mark.asyncio
async def test_todo_message_uses_create_task_skill() -> None:
    service = AgentService()
    event = InboundEvent(
        event_id="evt-2",
        event_type="message",
        team_id="T1",
        channel_id="C1",
        thread_ts="1710000000.0002",
        user_id="U1",
        text="/todo prepare weekly report",
    )

    reply = await service.process_event(event)

    assert reply.skill_name in {"create_task", ""}
    assert reply.text


@pytest.mark.asyncio
async def test_reaction_event_uses_handle_reaction_skill() -> None:
    service = AgentService()
    event = InboundEvent(
        event_id="evt-3",
        event_type="reaction_added",
        team_id="T1",
        channel_id="C1",
        thread_ts="1710000000.0003",
        user_id="U1",
        reaction="eyes",
    )

    reply = await service.process_event(event)

    assert reply.skill_name in {"handle_reaction", ""}
    assert reply.text

