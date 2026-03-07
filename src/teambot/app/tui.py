from __future__ import annotations

import argparse
import os
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from rich.columns import Columns
from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import Input, Static

from ..actions.tools.profiles import (
    TOOL_PROFILE_EXTERNAL_OPERATION,
    TOOL_PROFILE_FULL,
    TOOL_PROFILE_MINIMAL,
    describe_profiles,
)
from ..agent.service import AgentService
from ..domain.models import InboundEvent, RuntimeEvent
from .bootstrap import build_agent_service
from .slash_commands import dispatch_slash_command, format_help_lines


_ActivityKind = Literal["tool", "result"]


@dataclass
class _ActivityItem:
    kind: _ActivityKind
    text: str
    live: bool = False


@dataclass
class _RunTranscript:
    user_text: str
    activities: list[_ActivityItem] = field(default_factory=list)
    final_text: str = ""
    final_live: bool = False


class TranscriptRenderer:
    def __init__(self, *, workspace: str | None = None, model_name: str | None = None) -> None:
        self.workspace = workspace or str(Path.cwd())
        self.model_name = model_name or (os.getenv("AGENT_MODEL", "").strip() or "model not configured")
        self._runs: list[_RunTranscript] = []

    def begin_task(self, raw: str) -> None:
        self._runs.append(_RunTranscript(user_text=raw))

    def has_runs(self) -> bool:
        return bool(self._runs)

    def handle_event(self, event: RuntimeEvent) -> None:
        run = self._current_run()
        if run is None:
            return
        if event.event_type == "thinking":
            return
        if event.event_type == "thinking_delta":
            return
        if event.event_type == "tool_call":
            run.activities.append(
                _ActivityItem(
                    kind="tool",
                    text=self._format_action_summary(event.action_name, event.action_input, event.blocked),
                )
            )
            return
        if event.event_type == "tool_result":
            observation = event.observation or event.text or "(empty)"
            run.activities.append(
                _ActivityItem(kind="result", text=f"observed {self._truncate(observation)}")
            )
            return
        if event.event_type == "final_delta":
            run.final_text += event.text
            run.final_live = True
            return
        if event.event_type in {"final_text", "run_completed"}:
            final_text = (event.text or run.final_text).strip()
            if final_text:
                run.final_text = final_text
            return

    def render_text(self) -> str:
        if not self._runs:
            return "\n".join(
                [
                    "Welcome back!",
                    f"Workspace: {self.workspace}",
                    f"Model: {self.model_name}",
                    "Tips for getting started",
                    "- /skills",
                    "- /newthread",
                ]
            )

        lines: list[str] = []
        for index, run in enumerate(self._runs):
            if index > 0:
                lines.append("")
            lines.append(f"> {run.user_text}")
            for activity in run.activities:
                text = activity.text.strip()
                if not text:
                    continue
                lines.append(f"  {text}")
            if run.final_text.strip():
                lines.append(f"• {run.final_text.strip()}")
        return "\n".join(lines).strip()

    def render_rich(self, *, pulse_frame: int = 0) -> RenderableType:
        if not self._runs:
            return self._render_welcome()

        blocks: list[RenderableType] = []
        for index, run in enumerate(self._runs):
            if index > 0:
                blocks.append(Text(""))
            blocks.append(Text(f"> {run.user_text}", style="bold #f5f1e8"))
            for activity in run.activities:
                blocks.append(self._render_activity(activity, pulse_frame=pulse_frame))
            if run.final_text.strip():
                final_style = "bold #f7f0e8"
                if run.final_live and pulse_frame % 2:
                    final_style = "bold #ffd7a8"
                blocks.append(Text(f"• {run.final_text.strip()}", style=final_style))
        return Group(*blocks)

    def _render_welcome(self) -> RenderableType:
        intro = Table.grid(padding=(0, 1))
        intro.add_row(Text("Welcome back!", style="bold #f7f0e8"))
        intro.add_row(Text(f"TeamBot workbench  {self.model_name}", style="#d28f6c"))
        intro.add_row(Text(self._shorten_path(self.workspace), style="dim #d2c6b2"))

        tips = Table.grid(padding=(0, 1))
        tips.add_row(Text("Tips for getting started", style="bold #d28f6c"))
        tips.add_row(Text("Run /skills to inspect active skill context", style="#d2c6b2"))
        tips.add_row(Text("Type a task below to start a new run", style="#d2c6b2"))

        return Panel(
            Columns(
                [
                    intro,
                    tips,
                ],
                equal=True,
                expand=True,
            ),
            border_style="#6f5846",
            padding=(0, 1),
        )

    def _render_activity(self, activity: _ActivityItem, *, pulse_frame: int) -> RenderableType:
        return Text(f"  {activity.text.strip()}", style="dim #8d867f")

    def _current_run(self) -> _RunTranscript | None:
        if not self._runs:
            return None
        return self._runs[-1]

    @staticmethod
    def _format_action_summary(
        action_name: str,
        action_input: dict[str, Any],
        blocked: bool,
    ) -> str:
        summary = f"used {action_name or 'unknown'}"
        parts: list[str] = []
        for key in sorted(action_input):
            value = TranscriptRenderer._truncate(str(action_input[key]), limit=40)
            parts.append(f"{key}={value}")
        if parts:
            summary = f"{summary} ({', '.join(parts)})"
        if blocked:
            summary += " [blocked]"
        return summary

    @staticmethod
    def _truncate(value: str, *, limit: int = 100) -> str:
        collapsed = " ".join(value.split())
        if len(collapsed) <= limit:
            return collapsed
        return f"{collapsed[: limit - 3]}..."

    @staticmethod
    def _shorten_path(path: str, *, limit: int = 56) -> str:
        if len(path) <= limit:
            return path
        return f"...{path[-(limit - 3):]}"


class TeamBotTuiApp(App[None]):
    CSS = """
    Screen {
        background: #111111;
        color: #f5f1e8;
        layout: vertical;
    }

    #titlebar {
        height: auto;
        padding: 0 3;
        color: #8e8378;
    }

    #body {
        height: 1fr;
        padding: 0 3 0 3;
    }

    #transcript-scroll {
        height: 1fr;
    }

    #transcript {
        padding: 0 0 0 0;
    }

    #composer-shell {
        height: auto;
        padding: 0 3 1 3;
    }

    #composer-row {
        height: auto;
        background: #1a1a1a;
        border: round #5a4a40;
        padding: 0 1;
    }

    #composer-prompt {
        width: 3;
        content-align: center middle;
        color: #d28f6c;
    }

    Input {
        background: #1a1a1a;
        color: #f5f1e8;
        border: none;
        padding: 0 0 0 0;
    }
    """

    BINDINGS = [("ctrl+c", "quit", "Quit")]

    def __init__(
        self,
        *,
        team_id: str = "T1",
        channel_id: str = "C1",
        thread_ts: str = "1710000000.0001",
        user_id: str = "U1",
        service: AgentService | None = None,
    ) -> None:
        super().__init__()
        self.team_id = team_id
        self.channel_id = channel_id
        self.thread_ts = thread_ts
        self.user_id = user_id
        self.service = service or build_agent_service()
        self.transcript = TranscriptRenderer()
        self._status = "ready"
        self._stream_live = True
        self._pulse_frame = 0

    def compose(self) -> ComposeResult:
        yield Static(self._status_line(), id="titlebar")
        with Container(id="body"):
            with VerticalScroll(id="transcript-scroll"):
                yield Static(self.transcript.render_rich(), id="transcript")
        with Container(id="composer-shell"):
            with Horizontal(id="composer-row"):
                yield Static(">", id="composer-prompt")
                yield Input(placeholder="Ask TeamBot or use /command", id="composer")

    def on_mount(self) -> None:
        self.set_interval(0.4, self._tick_pulse)
        self.call_after_refresh(self._sync_scroll_mode)

    def _tick_pulse(self) -> None:
        self._pulse_frame = (self._pulse_frame + 1) % 8
        if self._status == "running":
            self._refresh_transcript()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        raw = event.value.strip()
        event.input.value = ""
        if not raw:
            return
        if await self._handle_command(raw):
            return
        await self._process_task(raw)

    async def _handle_command(self, raw: str) -> bool:
        action = dispatch_slash_command(
            raw,
            supports_debug=False,
            reload_runtime=self.service.reload_runtime,
        )
        if not action.handled:
            return False
        if raw == "/help":
            self._set_transcript(
                Panel(
                    "\n".join(format_help_lines(supports_debug=False)[1:]),
                    title="Commands",
                    border_style="#6f5846",
                )
            )
        else:
            self._apply_slash_action(action)
        return True

    def _apply_slash_action(self, action) -> None:
        if action.exit_requested:
            self.exit()
            return
        if action.new_thread_ts:
            self.thread_ts = action.new_thread_ts
            self._status = "new thread"
            self._refresh_status()
            self._set_transcript(Text(f"[system] switched to thread_ts={self.thread_ts}", style="#d2c6b2"))
            return
        if action.stream_enabled is not None:
            self._stream_live = action.stream_enabled
            self._refresh_status()
            self._refresh_transcript()
            return
        if action.output_lines:
            self._set_transcript(Text("\n".join(action.output_lines), style="#d2c6b2"))

    async def _process_task(self, raw: str) -> None:
        self._status = "running"
        self._refresh_status()
        self.transcript.begin_task(raw)
        self._refresh_transcript()
        event = self._build_event(raw)
        if event is None:
            self._status = "ready"
            self._refresh_status()
            return
        try:
            async for runtime_event in self.service.stream_event(event):
                if not self._stream_live and runtime_event.event_type in {"thinking_delta", "final_delta"}:
                    continue
                self.transcript.handle_event(runtime_event)
                self._refresh_transcript()
        finally:
            self._status = "ready"
            self._refresh_status()

    def _build_event(self, raw: str) -> InboundEvent | None:
        event_id = f"tui-{uuid.uuid4().hex[:12]}"
        if raw.startswith("/reaction "):
            reaction = raw.split(" ", 1)[1].strip()
            if not reaction:
                self._set_transcript(Text("[error] reaction name is required, e.g. /reaction eyes", style="#d2c6b2"))
                return None
            return InboundEvent(
                event_id=event_id,
                event_type="reaction_added",
                team_id=self.team_id,
                channel_id=self.channel_id,
                thread_ts=self.thread_ts,
                user_id=self.user_id,
                reaction=reaction,
            )
        return InboundEvent(
            event_id=event_id,
            event_type="message",
            team_id=self.team_id,
            channel_id=self.channel_id,
            thread_ts=self.thread_ts,
            user_id=self.user_id,
            text=raw,
        )

    def _refresh_transcript(self) -> None:
        self._sync_scroll_mode()
        self._set_transcript(self.transcript.render_rich(pulse_frame=self._pulse_frame))

    def _sync_scroll_mode(self) -> None:
        scroll = self.query_one("#transcript-scroll", VerticalScroll)
        has_runs = self.transcript.has_runs()
        scroll.styles.overflow_y = "auto" if has_runs else "hidden"
        scroll.show_vertical_scrollbar = has_runs

    def _set_transcript(self, renderable: RenderableType) -> None:
        transcript = self.query_one("#transcript", Static)
        transcript.update(renderable)

    def _refresh_status(self) -> None:
        status = self.query_one("#titlebar", Static)
        status.update(self._status_line())

    def _status_line(self) -> str:
        workspace = TranscriptRenderer._shorten_path(str(Path.cwd()), limit=72)
        if self._status == "running":
            return f"{workspace}> TeamBot · working"
        return f"{workspace}> TeamBot"

def parse_args() -> argparse.Namespace:
    profile_descriptions = describe_profiles()
    profile_help = (
        "Override runtime tool profile for this TUI session.\n"
        f"- {TOOL_PROFILE_MINIMAL}: {profile_descriptions[TOOL_PROFILE_MINIMAL]}\n"
        f"- {TOOL_PROFILE_EXTERNAL_OPERATION}: {profile_descriptions[TOOL_PROFILE_EXTERNAL_OPERATION]}\n"
        f"- {TOOL_PROFILE_FULL}: {profile_descriptions[TOOL_PROFILE_FULL]}"
    )
    parser = argparse.ArgumentParser(description="TeamBot Textual TUI")
    parser.add_argument("--team-id", default="T1")
    parser.add_argument("--channel-id", default="C1")
    parser.add_argument("--thread-ts", default="1710000000.0001")
    parser.add_argument("--user-id", default="U1")
    parser.add_argument(
        "--tools-profile",
        choices=[
            TOOL_PROFILE_MINIMAL,
            TOOL_PROFILE_EXTERNAL_OPERATION,
            TOOL_PROFILE_FULL,
        ],
        default=None,
        help=profile_help,
    )
    parser.add_argument(
        "--tools-config",
        default=None,
        help="Path to tools JSON config (profile + per-tool overrides).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    service = build_agent_service(
        tools_config_path=args.tools_config,
        tools_profile=args.tools_profile,
        strict_tools_config=bool(args.tools_config),
    )
    app = TeamBotTuiApp(
        team_id=args.team_id,
        channel_id=args.channel_id,
        thread_ts=args.thread_ts,
        user_id=args.user_id,
        service=service,
    )
    app.run()


if __name__ == "__main__":
    main()
