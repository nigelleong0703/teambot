from __future__ import annotations

from dataclasses import dataclass
import sys

import pytest

from teambot.app.cli import TeamBotCli, parse_args
from teambot.domain.models import OutboundReply, ReplyTarget, RuntimeEvent


@dataclass
class _ToolRegistryStub:
    def list_manifests(self) -> list[object]:
        return []


class _ServiceStub:
    def __init__(self) -> None:
        self.tool_registry = _ToolRegistryStub()
        self.listener = None
        self.runtime_events: list[RuntimeEvent] = []

    def set_model_event_listener(self, listener) -> None:
        self.listener = listener

    def reload_runtime(self) -> None:
        return None

    async def stream_event(self, _event):
        for item in self.runtime_events:
            yield item


def _build_cli(service: _ServiceStub) -> TeamBotCli:
    return TeamBotCli(
        team_id="T1",
        channel_id="C1",
        thread_ts="1710000000.0001",
        user_id="U1",
        service=service,  # type: ignore[arg-type]
    )


def _reply() -> OutboundReply:
    return OutboundReply(
        event_id="evt-1",
        conversation_key="T1:C1:1.1",
        reply_target=ReplyTarget(team_id="T1", channel_id="C1", thread_ts="1.1"),
        text="It is 10:30 now.",
        skill_name="get_current_time",
        reasoning_note="Need the current time before answering.",
        execution_trace=[
            {
                "step": 1,
                "action": "get_current_time",
                "input": {"timezone": "Asia/Kuala_Lumpur"},
                "blocked": False,
                "observation": "2026-03-06 10:30:00",
            }
        ],
    )


def test_cli_registers_model_listener_for_transcript_view() -> None:
    service = _ServiceStub()
    _build_cli(service)

    assert service.listener is not None


def test_cli_generates_new_thread_ts_when_not_provided() -> None:
    service = _ServiceStub()
    cli = TeamBotCli(
        team_id="T1",
        channel_id="C1",
        thread_ts=None,
        user_id="U1",
        service=service,  # type: ignore[arg-type]
    )

    assert cli.thread_ts
    assert cli.thread_ts != "1710000000.0001"


def test_cli_renders_transcript_sections(capsys) -> None:
    service = _ServiceStub()
    cli = _build_cli(service)

    cli._begin_task("check the current time")
    cli._render_followup(_reply())

    captured = capsys.readouterr().out
    assert "Task" in captured
    assert "Thinking" in captured
    assert "Tool" in captured
    assert "Result" in captured
    assert "Final" in captured
    assert "get_current_time timezone=Asia/Kuala_Lumpur" in captured
    assert "2026-03-06 10:30:00" in captured


def test_cli_does_not_handle_removed_mode_command(capsys) -> None:
    service = _ServiceStub()
    cli = _build_cli(service)

    handled = cli._handle_command("/mode chat")

    assert handled is False
    assert capsys.readouterr().out == ""


def test_parse_args_rejects_removed_ui_mode_flag(monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", ["teambot-cli", "--ui-mode", "chat"])

    with pytest.raises(SystemExit):
        parse_args()


def test_cli_does_not_repeat_final_text_when_streamed_live(capsys) -> None:
    service = _ServiceStub()
    cli = TeamBotCli(
        team_id="T1",
        channel_id="C1",
        thread_ts="1710000000.0001",
        user_id="U1",
        stream_model_tokens=True,
        service=service,  # type: ignore[arg-type]
    )

    cli._begin_task("say hello")
    cli._on_model_event(
        "model_start",
        {"role": "agent_model", "provider": "openai-compatible", "model": "gpt-test"},
    )
    cli._on_model_event("model_token", {"token": "Hello"})
    cli._on_model_event("model_end", {})
    cli._render_followup(
        OutboundReply(
            event_id="evt-2",
            conversation_key="T1:C1:1.1",
            reply_target=ReplyTarget(team_id="T1", channel_id="C1", thread_ts="1.1"),
            text="Hello",
            skill_name="",
            reasoning_note="Reasoner route: final answer",
            execution_trace=[],
        )
    )

    captured = capsys.readouterr().out
    assert "Final (live)" in captured
    assert captured.count("Hello") == 1
    assert "(streamed live above)" in captured


def test_cli_streams_reasoning_tokens_into_thinking_section(capsys) -> None:
    service = _ServiceStub()
    cli = TeamBotCli(
        team_id="T1",
        channel_id="C1",
        thread_ts="1710000000.0001",
        user_id="U1",
        stream_model_tokens=True,
        service=service,  # type: ignore[arg-type]
    )

    cli._begin_task("what time is it")
    cli._on_model_event(
        "model_start",
        {"role": "agent_model", "provider": "openai-compatible", "model": "gpt-test"},
    )
    cli._on_model_event("model_reasoning_token", {"token": "Need "})
    cli._on_model_event("model_reasoning_token", {"token": "current time"})
    cli._on_model_event("model_end", {})
    cli._render_followup(_reply())

    captured = capsys.readouterr().out
    assert "Thinking" in captured
    assert "Need current time" in captured
    assert "[reason]" not in captured


@pytest.mark.asyncio
async def test_cli_renders_runtime_event_timeline(capsys) -> None:
    service = _ServiceStub()
    service.runtime_events = [
        RuntimeEvent(run_id="run-1", step=1, event_type="thinking", text="Need current time"),
        RuntimeEvent(
            run_id="run-1",
            step=1,
            event_type="tool_call",
            action_name="get_current_time",
            action_input={"timezone": "Asia/Kuala_Lumpur"},
        ),
        RuntimeEvent(
            run_id="run-1",
            step=1,
            event_type="tool_result",
            action_name="get_current_time",
            observation="2026-03-07 21:30:00",
        ),
        RuntimeEvent(run_id="run-1", step=1, event_type="memory_compacted", text="Compacted summary"),
        RuntimeEvent(run_id="run-1", step=2, event_type="thinking", text="Now I can answer"),
        RuntimeEvent(run_id="run-1", step=2, event_type="run_completed", text="It is 9:30 PM."),
    ]
    cli = _build_cli(service)

    await cli._process_task("what time is it")

    captured = capsys.readouterr().out
    assert "Step 1 · Thinking" in captured
    assert "Step 1 · Tool" in captured
    assert "Step 1 · Result" in captured
    assert "Step 1 · Memory" in captured
    assert "Compacted summary" in captured
    assert "Step 2 · Thinking" in captured
    assert "Step 2 · Final" in captured
    assert "It is 9:30 PM." in captured
