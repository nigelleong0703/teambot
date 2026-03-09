from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import sys
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

from ..actions.tools.profiles import (
    TOOL_PROFILE_EXTERNAL_OPERATION,
    TOOL_PROFILE_FULL,
    TOOL_PROFILE_MINIMAL,
    describe_profiles,
)
from ..agent.service import AgentService
from ..domain.models import InboundEvent, OutboundReply, RuntimeEvent
from ..runtime_paths import get_agent_work_dir
from ..skills.manager import SkillService
from .bootstrap import build_agent_service
from .slash_commands import SlashCommandAction, dispatch_slash_command


_ActivityKind = Literal["tool", "result"]
_RESET = "\033[0m"
_CLEAR_LINE = "\r\033[2K"
_ANSI_STYLES = {
    "accent": "\033[38;5;180m",
    "border": "\033[38;5;240m",
    "dim": "\033[38;5;244m",
    "final": "\033[38;5;230m",
    "thinking_head": "\033[1;38;5;229m",
    "prompt": "\033[38;5;215m",
    "thinking": "\033[38;5;221m",
    "tool": "\033[38;5;111m",
    "result": "\033[38;5;246m",
    "system": "\033[38;5;150m",
    "error": "\033[38;5;203m",
}


@dataclass
class _ActivityItem:
    kind: _ActivityKind
    text: str


@dataclass
class _RunTranscript:
    user_text: str
    activities: list[_ActivityItem] = field(default_factory=list)
    thinking_active: bool = False
    final_text: str = ""


class TranscriptRenderer:
    def __init__(
        self,
        *,
        workspace: str | None = None,
        model_name: str | None = None,
        loaded_skills_count: int = 0,
        stream_enabled: bool = True,
        terminal_width: int | None = None,
    ) -> None:
        self.workspace = workspace or str(get_agent_work_dir())
        self.model_name = model_name or (os.getenv("AGENT_MODEL", "").strip() or "model not configured")
        self.loaded_skills_count = loaded_skills_count
        self.stream_enabled = stream_enabled
        self.terminal_width = terminal_width or shutil.get_terminal_size(fallback=(120, 24)).columns
        self._runs: list[_RunTranscript] = []

    def begin_task(self, raw: str) -> None:
        self._runs.append(_RunTranscript(user_text=raw, thinking_active=True))

    def has_runs(self) -> bool:
        return bool(self._runs)

    def handle_event(self, event: RuntimeEvent) -> None:
        run = self._current_run()
        if run is None:
            return
        if event.event_type in {"thinking", "thinking_delta"}:
            run.thinking_active = True
            return
        if event.event_type == "tool_call":
            run.thinking_active = False
            run.activities.append(
                _ActivityItem(
                    kind="tool",
                    text=self._format_action_summary(event.action_name, event.action_input, event.blocked),
                )
            )
            return
        if event.event_type == "tool_result":
            run.thinking_active = False
            observation = event.observation or event.text or "(empty)"
            run.activities.append(_ActivityItem(kind="result", text=f"observed {self._truncate(observation)}"))
            return
        if event.event_type == "final_delta":
            run.thinking_active = False
            run.final_text += event.text
            return
        if event.event_type in {"final_text", "run_completed"}:
            run.thinking_active = False
            final_text = (event.text or run.final_text).strip()
            if final_text:
                run.final_text = final_text

    def render_text(self) -> str:
        if not self._runs:
            return self.render_welcome()

        lines: list[str] = []
        for index, run in enumerate(self._runs):
            if index > 0:
                lines.append("")
            lines.append(f"❯  {run.user_text}")
            if run.thinking_active and not run.final_text.strip():
                lines.append("")
                lines.append("✻ Thinking...")
            for activity in run.activities:
                lines.append(self._render_activity_line(activity))
            if run.final_text.strip():
                lines.append("")
                lines.append(f"⏺ {run.final_text.strip()}")
        return "\n".join(lines).strip()

    def render_welcome(self) -> str:
        inner_width = max(40, min(108, self.terminal_width - 4))
        column_width = (inner_width - 3) // 2
        if inner_width < 104 or column_width < 40:
            return self._render_compact_welcome(inner_width)

        value_width = max(18, column_width - 4)
        left = [
            "",
            "TeamBot",
            "",
            "Model",
            self._truncate(self.model_name, limit=value_width),
            "",
            "Agent work dir",
            self._shorten_path(self.workspace, limit=value_width),
        ]
        right = [
            "Runtime status",
            f"Skills loaded: {self.loaded_skills_count}",
            "-" * max(12, column_width - 4),
            f"Streaming: {'on' if self.stream_enabled else 'off'}",
            self._truncate(
                f"Toggle: {'/stream off' if self.stream_enabled else '/stream on'}",
                limit=value_width,
            ),
            "",
            "Quick commands",
            "/skills",
            "/newthread",
            "/exit",
        ]
        return self._render_box(
            title="TeamBot Workbench",
            left_lines=left,
            right_lines=right,
            inner_width=inner_width,
        )

    def _render_compact_welcome(self, inner_width: int) -> str:
        value_width = max(12, inner_width - 18)
        lines = [
            self._center("TeamBot", inner_width),
            "",
            f"Model: {self._truncate(self.model_name, limit=value_width)}",
            f"Skills: {self.loaded_skills_count} loaded",
            f"Streaming: {'on' if self.stream_enabled else 'off'}",
            f"Toggle: {'/stream off' if self.stream_enabled else '/stream on'}",
            f"Work dir: {self._shorten_path(self.workspace, limit=value_width)}",
            "",
            "Commands:",
            "/skills",
            "/newthread",
            "/exit",
        ]
        return self._render_single_column_box(
            title="TeamBot Workbench",
            lines=lines,
            inner_width=inner_width,
        )

    @staticmethod
    def _render_activity_line(activity: _ActivityItem) -> str:
        if activity.kind == "tool":
            return f"⎿ {activity.text.strip()}"
        return f"  {activity.text.strip()}"

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

    @staticmethod
    def _center(text: str, width: int) -> str:
        trimmed = text[:width]
        return trimmed.center(width)

    @classmethod
    def _render_box(
        cls,
        *,
        title: str,
        left_lines: list[str],
        right_lines: list[str],
        inner_width: int,
    ) -> str:
        column_width = (inner_width - 3) // 2
        top = f"╭─── {title} " + "─" * max(1, inner_width - len(title) - 5) + "╮"
        body: list[str] = []
        rows = max(len(left_lines), len(right_lines))
        for index in range(rows):
            left = left_lines[index] if index < len(left_lines) else ""
            right = right_lines[index] if index < len(right_lines) else ""
            if index in {1, 7, 8}:
                left = cls._center(left, column_width)
            else:
                left = left[:column_width].ljust(column_width)
            right = right[:column_width].ljust(column_width)
            body.append(f"│ {left} │ {right} │")
        bottom = "╰" + "─" * (inner_width + 2) + "╯"
        return "\n".join([top, *body, bottom])

    @classmethod
    def _render_single_column_box(
        cls,
        *,
        title: str,
        lines: list[str],
        inner_width: int,
    ) -> str:
        top = f"╭─── {title} " + "─" * max(1, inner_width - len(title) - 5) + "╮"
        body = [f"│ {line[:inner_width].ljust(inner_width)} │" for line in lines]
        bottom = "╰" + "─" * (inner_width + 2) + "╯"
        return "\n".join([top, *body, bottom])

    def _current_run(self) -> _RunTranscript | None:
        if not self._runs:
            return None
        return self._runs[-1]


class TeamBotTuiApp:
    def __init__(
        self,
        *,
        team_id: str = "T1",
        channel_id: str = "C1",
        thread_ts: str = "1710000000.0001",
        user_id: str = "U1",
        service: AgentService | None = None,
    ) -> None:
        self.team_id = team_id
        self.channel_id = channel_id
        self.thread_ts = thread_ts
        self.user_id = user_id
        self.service = service or build_agent_service()
        self._status = "ready"
        self._stream_live = True
        self._exit_requested = False
        self._use_color = self._supports_color()
        self.transcript = TranscriptRenderer(
            loaded_skills_count=len(SkillService.list_available_skill_docs()),
            stream_enabled=self._stream_live,
        )

    async def run(self) -> None:
        self._print_startup()
        while True:
            try:
                raw = input(self._style("❯  ", "prompt")).strip()
            except EOFError:
                print()
                break
            except KeyboardInterrupt:
                print()
                break

            if not raw:
                continue
            if await self._handle_command(raw):
                if self._exit_requested:
                    break
                continue

            try:
                await self._process_task(raw)
            except KeyboardInterrupt:
                self._status = "ready"
                print()
                print("[interrupted]")

    async def _handle_command(self, raw: str) -> bool:
        action = dispatch_slash_command(
            raw,
            supports_debug=False,
            reload_runtime=self.service.reload_runtime,
        )
        if not action.handled:
            return False
        self._apply_slash_action(action)
        return True

    def _apply_slash_action(self, action: SlashCommandAction) -> None:
        self._exit_requested = action.exit_requested
        if action.new_thread_ts:
            self.thread_ts = action.new_thread_ts
            self._print_line(f"[system] switched to thread_ts={self.thread_ts}", kind="system")
        if action.stream_enabled is not None:
            self._stream_live = action.stream_enabled
            self.transcript.stream_enabled = action.stream_enabled
            self._print_line(f"[system] stream_model_tokens={self._stream_live}", kind="system")
        for line in action.output_lines:
            self._print_line(line, kind="system")

    async def _process_task(self, raw: str) -> None:
        event = self._build_event(raw)
        if event is None:
            return

        self._status = "running"
        self.transcript.begin_task(raw)
        print()

        thinking_task: asyncio.Task[None] | None = None
        thinking_stop = asyncio.Event()
        if self._can_animate_thinking():
            thinking_task = asyncio.create_task(self._animate_thinking(thinking_stop))
        else:
            self._print_line("✻ Thinking...", kind="thinking")
        thinking_shown = True
        final_stream_open = False
        final_buffer: list[str] = []
        pending_final_text = ""
        streamed_any = False

        try:
            async for runtime_event in self.service.stream_event(event):
                streamed_any = True
                self.transcript.handle_event(runtime_event)

                if runtime_event.event_type in {"thinking", "thinking_delta"}:
                    if not thinking_shown:
                        self._print_line("✻ Thinking...", kind="thinking")
                        thinking_shown = True
                    continue

                if runtime_event.event_type == "tool_call":
                    await self._stop_thinking_animation(thinking_stop, thinking_task)
                    self._print_line(
                        f"⎿ {self._format_trace_action(runtime_event.action_name, runtime_event.action_input, runtime_event.blocked)}",
                        kind="tool",
                    )
                    continue

                if runtime_event.event_type == "tool_result":
                    await self._stop_thinking_animation(thinking_stop, thinking_task)
                    observation = self._truncate(runtime_event.observation or runtime_event.text or "(empty)")
                    self._print_line(f"  {observation}", kind="result")
                    continue

                if runtime_event.event_type == "final_delta":
                    token = runtime_event.text
                    if not token:
                        continue
                    await self._stop_thinking_animation(thinking_stop, thinking_task)
                    if not final_stream_open:
                        print(self._style("⏺ ", "final"), end="", flush=True)
                        final_stream_open = True
                    print(self._style(token, "final"), end="", flush=True)
                    final_buffer.append(token)
                    continue

                if runtime_event.event_type == "final_text":
                    pending_final_text = runtime_event.text
                    continue

                if runtime_event.event_type == "run_completed":
                    await self._stop_thinking_animation(thinking_stop, thinking_task)
                    final_text = (runtime_event.text or pending_final_text or "".join(final_buffer)).strip()
                    if final_stream_open:
                        print()
                    elif final_text:
                        self._print_line(f"⏺ {final_text}", kind="final")
                    break
        finally:
            await self._stop_thinking_animation(thinking_stop, thinking_task)

        if not streamed_any:
            reply = await self.service.process_event(event)
            self._render_followup(reply)

        print()
        self._status = "ready"

    def _render_followup(self, reply: OutboundReply) -> None:
        if reply.execution_trace:
            for item in reply.execution_trace:
                self._print_line(
                    f"⎿ {self._format_trace_action(str(item.get('action') or ''), item.get('input') if isinstance(item.get('input'), dict) else {}, bool(item.get('blocked')))}",
                    kind="tool",
                )
                observation = str(item.get("observation") or "").strip()
                if observation:
                    self._print_line(f"  {self._truncate(observation)}", kind="result")
        self._print_line(f"⏺ {reply.text}", kind="final")

    def _build_event(self, raw: str) -> InboundEvent | None:
        event_id = f"tui-{uuid.uuid4().hex[:12]}"
        if raw.startswith("/reaction "):
            reaction = raw.split(" ", 1)[1].strip()
            if not reaction:
                self._print_line("[error] reaction name is required, e.g. /reaction eyes", kind="error")
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

    def _print_startup(self) -> None:
        self._print_line(self._colorize_welcome(self.transcript.render_welcome()))

    def _status_line(self) -> str:
        return TranscriptRenderer._shorten_path(str(get_agent_work_dir()), limit=72)

    async def _animate_thinking(self, stop: asyncio.Event) -> None:
        frame = 0
        try:
            while not stop.is_set():
                sys.stdout.write(f"{_CLEAR_LINE}{self._thinking_frame(frame)}")
                sys.stdout.flush()
                frame += 1
                await asyncio.sleep(0.09)
        except asyncio.CancelledError:
            raise

    async def _stop_thinking_animation(
        self,
        stop: asyncio.Event,
        task: asyncio.Task[None] | None,
    ) -> None:
        if task is None or task.done():
            return
        stop.set()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        sys.stdout.write(_CLEAR_LINE)
        sys.stdout.flush()

    def _thinking_frame(self, frame: int) -> str:
        prefix = self._style("✻ ", "thinking")
        text = "Thinking..."
        trail = 3
        total = len(text) + trail + 1
        head = frame % total
        parts: list[str] = [prefix]
        for index, char in enumerate(text):
            distance = head - index
            if distance == 0:
                style = "thinking_head"
            elif 0 < distance <= trail:
                style = "thinking"
            else:
                style = "dim"
            parts.append(self._style(char, style))
        return "".join(parts)

    def _can_animate_thinking(self) -> bool:
        return self._use_color and sys.stdout.isatty()

    def _print_line(self, text: str, *, kind: str | None = None) -> None:
        print(self._style(text, kind))

    def _colorize_welcome(self, text: str) -> str:
        if not self._use_color:
            return text
        colored = text
        for char in ("╭", "╮", "╰", "╯", "─", "│"):
            colored = colored.replace(char, self._style(char, "border"))
        replacements = {
            "TeamBot": self._style("TeamBot", "final"),
            "Runtime status": self._style("Runtime status", "accent"),
            "Model": self._style("Model", "accent"),
            "Agent work dir": self._style("Agent work dir", "accent"),
            "Quick commands": self._style("Quick commands", "accent"),
            "Streaming: on": self._style("Streaming: on", "system"),
            "Streaming: off": self._style("Streaming: off", "dim"),
            "/stream on": self._style("/stream on", "tool"),
            "/stream off": self._style("/stream off", "tool"),
            "/skills": self._style("/skills", "tool"),
            "/newthread": self._style("/newthread", "tool"),
            "/exit": self._style("/exit", "tool"),
        }
        for plain, styled in replacements.items():
            colored = colored.replace(plain, styled)
        return colored

    def _style(self, text: str, kind: str | None = None) -> str:
        if not self._use_color or kind is None:
            return text
        prefix = _ANSI_STYLES.get(kind, "")
        if not prefix:
            return text
        return f"{prefix}{text}{_RESET}"

    @staticmethod
    def _supports_color() -> bool:
        if os.getenv("NO_COLOR"):
            return False
        term = os.getenv("TERM", "")
        return sys.stdout.isatty() and term.lower() != "dumb"

    @staticmethod
    def _format_trace_action(
        action_name: str,
        action_input: dict[str, Any],
        blocked: bool,
    ) -> str:
        parts: list[str] = [action_name or "unknown"]
        for key in sorted(action_input):
            parts.append(f"{key}={TeamBotTuiApp._summarize_value(action_input[key])}")
        if blocked:
            parts.append("[blocked]")
        return " ".join(parts)

    @staticmethod
    def _summarize_value(value: Any) -> str:
        if isinstance(value, (str, int, float, bool)) or value is None:
            return TeamBotTuiApp._truncate(str(value), limit=60)
        return TeamBotTuiApp._truncate(json.dumps(value, ensure_ascii=False, default=str), limit=60)

    @staticmethod
    def _truncate(value: str, *, limit: int = 160) -> str:
        collapsed = " ".join(value.split())
        if len(collapsed) <= limit:
            return collapsed
        return f"{collapsed[: limit - 3]}..."


def parse_args() -> argparse.Namespace:
    profile_descriptions = describe_profiles()
    profile_help = (
        "Override runtime tool profile for this terminal workbench session.\n"
        f"- {TOOL_PROFILE_MINIMAL}: {profile_descriptions[TOOL_PROFILE_MINIMAL]}\n"
        f"- {TOOL_PROFILE_EXTERNAL_OPERATION}: {profile_descriptions[TOOL_PROFILE_EXTERNAL_OPERATION]}\n"
        f"- {TOOL_PROFILE_FULL}: {profile_descriptions[TOOL_PROFILE_FULL]}"
    )
    parser = argparse.ArgumentParser(description="TeamBot terminal workbench")
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
    try:
        asyncio.run(app.run())
    except KeyboardInterrupt:
        print()


if __name__ == "__main__":
    main()
