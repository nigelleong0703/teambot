from __future__ import annotations

import pytest

from teambot.app.tui import TeamBotTuiApp, TranscriptRenderer
from teambot.domain.models import RuntimeEvent


def test_transcript_renderer_shows_welcome_state_before_any_task() -> None:
    renderer = TranscriptRenderer()

    text = renderer.render_text()

    assert "Welcome back!" in text
    assert "Tips for getting started" in text
    assert "/tools" not in text


def test_transcript_renderer_builds_claude_like_activity_summary() -> None:
    renderer = TranscriptRenderer()
    renderer.begin_task("what time is it")
    renderer.handle_event(RuntimeEvent(run_id="run-1", step=1, event_type="thinking", text="Need current time"))
    renderer.handle_event(
        RuntimeEvent(
            run_id="run-1",
            step=1,
            event_type="tool_call",
            action_name="get_current_time",
            action_input={"timezone": "Asia/Kuala_Lumpur"},
        )
    )
    renderer.handle_event(
        RuntimeEvent(
            run_id="run-1",
            step=1,
            event_type="tool_result",
            observation="2026-03-07 21:30:00",
        )
    )
    renderer.handle_event(RuntimeEvent(run_id="run-1", step=2, event_type="run_completed", text="It is 9:30 PM."))

    text = renderer.render_text()
    assert "> what time is it" in text
    assert "thinking" not in text.lower()
    assert "Need current time" not in text
    assert "used get_current_time" in text
    assert "observed 2026-03-07 21:30:00" in text
    assert "• It is 9:30 PM." in text
    assert "It is 9:30 PM." in text


def test_transcript_renderer_merges_live_deltas_into_step_sections() -> None:
    renderer = TranscriptRenderer()
    renderer.begin_task("check time")
    renderer.handle_event(RuntimeEvent(run_id="run-1", step=1, event_type="thinking", text="Need"))
    renderer.handle_event(RuntimeEvent(run_id="run-1", step=1, event_type="thinking_delta", text=" current"))
    renderer.handle_event(RuntimeEvent(run_id="run-1", step=1, event_type="thinking_delta", text=" time"))
    renderer.handle_event(RuntimeEvent(run_id="run-1", step=1, event_type="final_delta", text="It "))
    renderer.handle_event(RuntimeEvent(run_id="run-1", step=1, event_type="final_delta", text="is "))
    renderer.handle_event(RuntimeEvent(run_id="run-1", step=1, event_type="final_delta", text="9:30 PM."))
    renderer.handle_event(RuntimeEvent(run_id="run-1", step=1, event_type="run_completed", text=""))

    text = renderer.render_text()
    assert "thinking" not in text.lower()
    assert "Need current time" not in text
    assert "• It is 9:30 PM." in text


def test_tui_app_exposes_transcript_renderer() -> None:
    app = TeamBotTuiApp()

    assert isinstance(app.transcript, TranscriptRenderer)


def test_tui_status_line_is_minimal_and_not_telemetry_heavy() -> None:
    app = TeamBotTuiApp()

    status = app._status_line()

    assert "teambot" in status.lower()
    assert "live" not in status.lower()
    assert "settled" not in status.lower()
    assert "ready" not in status.lower()


def test_transcript_renderer_tracks_whether_runs_exist() -> None:
    renderer = TranscriptRenderer()

    assert renderer.has_runs() is False
    renderer.begin_task("hello")
    assert renderer.has_runs() is True


@pytest.mark.asyncio
async def test_tui_does_not_handle_removed_tools_command() -> None:
    app = TeamBotTuiApp()

    handled = await app._handle_command("/tools")

    assert handled is False
