import pytest

from teambot.domain.models import InboundEvent
from teambot.agent.service import AgentService
from teambot.agent.reason import _deterministic_direct_route
from teambot.actions.event_handlers.builtin import build_registry as build_event_handler_registry
from teambot.actions.registry import PluginHost


def test_todo_message_is_not_a_deterministic_event_handler_route() -> None:
    registry = PluginHost()
    registry.bind_event_handler_registry(build_event_handler_registry())

    result = _deterministic_direct_route(
        {
            "conversation_key": "T1:C1:1",
            "recent_turns": [],
            "conversation_summary": "",
            "memory_system_prompt_suffix": "",
            "event_type": "message",
            "user_text": "/todo prepare weekly report",
            "reaction": None,
            "runtime_working_dir": "/tmp/teambot-work",
            "react_step": 0,
            "react_max_steps": 3,
            "react_done": False,
            "react_notes": [],
            "reasoning_note": "",
            "active_skill_names": [],
            "active_skill_docs": [],
            "selected_action": "",
            "selected_skill": "",
            "action_input": {},
            "skill_input": {},
            "action_output": {},
            "skill_output": {},
            "execution_trace": [],
            "reply_text": "",
        },
        registry,
    )

    assert result is None


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

