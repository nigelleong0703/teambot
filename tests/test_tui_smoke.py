from __future__ import annotations

from dataclasses import dataclass

import pytest

from teambot.app import tui_input
from teambot.app.tui import TeamBotTuiApp, TranscriptRenderer
from teambot.domain.models import OutboundReply, ReplyTarget, RuntimeEvent


@dataclass
class _ToolRegistryStub:
    def list_manifests(self) -> list[object]:
        return []


class _ServiceStub:
    def __init__(self) -> None:
        self.tool_registry = _ToolRegistryStub()
        self.runtime_events: list[RuntimeEvent] = []

    def reload_runtime(self) -> None:
        return None

    async def stream_event(self, _event):
        for item in self.runtime_events:
            yield item

    async def process_event(self, _event) -> OutboundReply:
        return OutboundReply(
            event_id="evt-1",
            conversation_key="conv-1",
            reply_target=ReplyTarget(team_id="T1", channel_id="C1", thread_ts="1"),
            text="fallback",
            skill_name="",
            reasoning_note="",
            execution_trace=[],
        )


@dataclass
class _InputReaderStub:
    responses: list[str]
    prompts: list[str]

    def read(self, prompt_text: str) -> str:
        self.prompts.append(prompt_text)
        if not self.responses:
            raise EOFError
        return self.responses.pop(0)


class _FakePromptSession:
    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.prompts: list[object] = []

    def prompt(self, prompt_text: object) -> str:
        self.prompts.append(prompt_text)
        return "composed message"


class _FakeANSI:
    def __init__(self, value: str) -> None:
        self.value = value


class _FakeHistory:
    pass


class _FakeKeyBindings:
    def __init__(self) -> None:
        self.bindings: list[tuple[str, ...]] = []

    def add(self, *keys: str):
        def decorator(func):
            self.bindings.append(keys)
            return func

        return decorator


def test_transcript_renderer_shows_terminal_welcome_state_before_any_task() -> None:
    renderer = TranscriptRenderer()

    text = renderer.render_text()

    assert "TeamBot" in text
    assert "Runtime status" in text
    assert "Skills loaded:" in text
    assert "Streaming: on" in text
    assert "/skills" in text
    assert "/tools" not in text


def test_transcript_renderer_switches_to_compact_welcome_on_narrow_terminal() -> None:
    renderer = TranscriptRenderer(terminal_width=100)

    text = renderer.render_text()

    assert "TeamBot" in text
    assert "Commands:" in text
    assert "Skills: " in text
    assert "│ TeamBot" not in text


def test_transcript_renderer_builds_terminal_native_summary() -> None:
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
    renderer.handle_event(
        RuntimeEvent(
            run_id="run-1",
            step=1,
            event_type="memory_compacted",
            text="Compacted summary",
        )
    )
    renderer.handle_event(RuntimeEvent(run_id="run-1", step=2, event_type="run_completed", text="It is 9:30 PM."))

    text = renderer.render_text()
    assert "❯  what time is it" in text
    assert "Need current time" not in text
    assert "used get_current_time" in text
    assert "observed 2026-03-07 21:30:00" in text
    assert "Compacted summary" in text
    assert "⏺ It is 9:30 PM." in text


def test_transcript_renderer_shows_thinking_before_final_answer() -> None:
    renderer = TranscriptRenderer()
    renderer.begin_task("hello")

    text = renderer.render_text()

    assert "❯  hello" in text
    assert "✻ Thinking..." in text


def test_transcript_renderer_merges_live_deltas_without_duplicate_final_text() -> None:
    renderer = TranscriptRenderer()
    renderer.begin_task("check time")
    renderer.handle_event(RuntimeEvent(run_id="run-1", step=1, event_type="thinking_delta", text=" current"))
    renderer.handle_event(RuntimeEvent(run_id="run-1", step=1, event_type="final_delta", text="It "))
    renderer.handle_event(RuntimeEvent(run_id="run-1", step=1, event_type="final_delta", text="is "))
    renderer.handle_event(RuntimeEvent(run_id="run-1", step=1, event_type="final_delta", text="9:30 PM."))
    renderer.handle_event(RuntimeEvent(run_id="run-1", step=1, event_type="run_completed", text=""))

    text = renderer.render_text()
    assert "✻ Thinking..." not in text
    assert "⏺ It is 9:30 PM." in text


def test_tui_app_exposes_terminal_transcript_renderer() -> None:
    app = TeamBotTuiApp()

    assert isinstance(app.transcript, TranscriptRenderer)
    assert app.thread_ts != "1710000000.0001"


def test_tui_status_line_is_workspace_path_only() -> None:
    app = TeamBotTuiApp()

    status = app._status_line()

    assert "TeamBot" not in status
    assert "live" not in status.lower()
    assert "ready" not in status.lower()


def test_tui_reads_from_injected_input_reader_and_preserves_multiline_text() -> None:
    reader = _InputReaderStub(
        responses=["  first line\nsecond line  "],
        prompts=[],
    )
    app = TeamBotTuiApp(
        service=_ServiceStub(),  # type: ignore[arg-type]
        input_reader=reader,  # type: ignore[arg-type]
    )

    raw = app._read_user_input()
    event = app._build_event(raw)

    assert raw == "first line\nsecond line"
    assert reader.prompts == ["❯  "]
    assert event is not None
    assert event.text == "first line\nsecond line"


def test_build_tui_input_reader_falls_back_to_plain_input_without_prompt_toolkit(monkeypatch) -> None:
    monkeypatch.setattr(tui_input, "_load_prompt_toolkit_modules", lambda: None)

    reader = tui_input.build_tui_input_reader(use_color=False)

    assert isinstance(reader, tui_input.PlainInputReader)


def test_build_tui_input_reader_uses_prompt_toolkit_multiline_session(monkeypatch) -> None:
    monkeypatch.setattr(
        tui_input,
        "_load_prompt_toolkit_modules",
        lambda: (_FakePromptSession, _FakeANSI, _FakeHistory, _FakeKeyBindings),
    )

    reader = tui_input.build_tui_input_reader(use_color=True)

    assert isinstance(reader, tui_input.PromptToolkitInputReader)
    assert reader.read("❯  ") == "composed message"
    assert isinstance(reader.session.prompts[0], _FakeANSI)
    assert reader.session.kwargs["multiline"] is True
    assert ("enter",) in reader.session.kwargs["key_bindings"].bindings
    assert ("escape", "enter") in reader.session.kwargs["key_bindings"].bindings
    assert ("c-j",) in reader.session.kwargs["key_bindings"].bindings


@pytest.mark.asyncio
async def test_tui_does_not_handle_removed_tools_command() -> None:
    app = TeamBotTuiApp()

    handled = await app._handle_command("/tools")

    assert handled is False


@pytest.mark.asyncio
async def test_tui_shows_thinking_even_without_reasoning_events(capsys) -> None:
    service = _ServiceStub()
    service.runtime_events = [
        RuntimeEvent(run_id="run-1", step=1, event_type="run_completed", text="done"),
    ]
    app = TeamBotTuiApp(service=service)  # type: ignore[arg-type]

    await app._process_task("hello")

    captured = capsys.readouterr().out
    assert "✻ Thinking..." in captured
    assert "⏺ done" in captured
