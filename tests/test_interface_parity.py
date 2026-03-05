from __future__ import annotations

from pathlib import Path

import pytest

from teambot.interfaces.bootstrap import build_agent_service
from teambot.domain.models import InboundEvent


ROOT = Path(__file__).resolve().parents[1]


def test_api_and_cli_use_bootstrap_composition_root() -> None:
    main_py = (ROOT / "src" / "teambot" / "app" / "main.py").read_text(encoding="utf-8")
    cli_py = (ROOT / "src" / "teambot" / "app" / "cli.py").read_text(encoding="utf-8")

    assert "from ..interfaces.bootstrap import build_agent_service" in main_py
    assert "from ..interfaces.bootstrap import build_agent_service" in cli_py
    assert "service = build_agent_service()" in main_py
    assert "service = build_agent_service(" in cli_py
    assert "Profiles:" in cli_py


@pytest.mark.asyncio
async def test_bootstrapped_service_handles_message_and_reaction() -> None:
    service = build_agent_service()

    message_event = InboundEvent(
        event_id="evt-msg-1",
        event_type="message",
        team_id="T1",
        channel_id="C1",
        thread_ts="1.1",
        user_id="U1",
        text="/todo write docs",
    )
    message_result = await service.process_event(message_event)
    assert message_result.skill_name in {"create_task", ""}
    assert message_result.text

    reaction_event = InboundEvent(
        event_id="evt-react-1",
        event_type="reaction_added",
        team_id="T1",
        channel_id="C1",
        thread_ts="1.1",
        user_id="U1",
        reaction="eyes",
    )
    reaction_reply = await service.process_event(reaction_event)
    assert reaction_reply.skill_name in {"handle_reaction", ""}
    assert reaction_reply.text

