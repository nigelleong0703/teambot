from __future__ import annotations

import argparse
import asyncio
import json
import uuid
from typing import Any

from ..agent.service import AgentService
from ..actions.tools.profiles import (
    TOOL_PROFILE_EXTERNAL_OPERATION,
    TOOL_PROFILE_FULL,
    TOOL_PROFILE_MINIMAL,
    describe_profiles,
)
from ..domain.models import InboundEvent, OutboundReply, RuntimeEvent
from .bootstrap import build_agent_service
from .slash_commands import SlashCommandAction, dispatch_slash_command, format_help_lines, new_thread_ts
from .terminal_io import discard_pending_stdin, suppress_stdin_echo


class TeamBotCli:
    def __init__(
        self,
        *,
        team_id: str,
        channel_id: str,
        thread_ts: str | None,
        user_id: str,
        stream_model_tokens: bool = False,
        show_model_payload: bool = False,
        service: AgentService | None = None,
    ) -> None:
        self.team_id = team_id
        self.channel_id = channel_id
        self.thread_ts = thread_ts or new_thread_ts()
        self.user_id = user_id
        self.service = service or build_agent_service()
        self._stream_model_tokens = stream_model_tokens
        self._show_model_payload = show_model_payload
        self._stream_line_open = False
        self._reasoning_line_open = False
        self._task_active = False
        self._thinking_printed = False
        self._last_streamed_text = ""
        self._active_stream_buffer: list[str] = []
        self._pending_final_text = ""
        self._exit_requested = False
        self._refresh_model_listener()

    async def run(self) -> None:
        self._print_help()
        while True:
            try:
                discard_pending_stdin()
                raw = input("task> ").strip()
            except EOFError:
                print()
                break
            except KeyboardInterrupt:
                print()
                break

            if not raw:
                continue
            if self._handle_command(raw):
                if self._exit_requested:
                    break
                continue

            await self._process_task(raw)

    async def _process_task(self, raw: str) -> None:
        event = self._build_event(raw)
        if event is None:
            return

        with suppress_stdin_echo():
            self._begin_task(raw)

            streamed_any = False
            if hasattr(self.service, "stream_event"):
                async for runtime_event in self.service.stream_event(event):
                    streamed_any = True
                    self._render_runtime_event(runtime_event)

            if not streamed_any:
                reply = await self.service.process_event(event)
                self._close_live_lines()
                self._render_followup(reply)

    def _build_event(self, raw: str) -> InboundEvent | None:
        event_id = f"cli-{uuid.uuid4().hex[:12]}"

        if raw.startswith("/reaction "):
            reaction = raw.split(" ", 1)[1].strip()
            if not reaction:
                print("[error] reaction name is required, e.g. /reaction eyes")
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

    @staticmethod
    def _print_help() -> None:
        profile_descriptions = describe_profiles()
        print("TeamBot CLI")
        for line in format_help_lines(supports_debug=True):
            print(line)
        print("Profiles:")
        print(f"  - {TOOL_PROFILE_MINIMAL}: {profile_descriptions[TOOL_PROFILE_MINIMAL]}")
        print(
            f"  - {TOOL_PROFILE_EXTERNAL_OPERATION}: "
            f"{profile_descriptions[TOOL_PROFILE_EXTERNAL_OPERATION]}"
        )
        print(f"  - {TOOL_PROFILE_FULL}: {profile_descriptions[TOOL_PROFILE_FULL]}")
        print("Default output:")
        print("  - transcript view with Task/Thinking/Tool/Result/Final")
        print("Input any other text to send a message event")

    def _handle_command(self, raw: str) -> bool:
        action = dispatch_slash_command(
            raw,
            supports_debug=True,
            reload_runtime=self.service.reload_runtime,
        )
        return self._apply_slash_action(action)

    def _apply_slash_action(self, action: SlashCommandAction) -> bool:
        if not action.handled:
            return False
        self._exit_requested = action.exit_requested
        if action.new_thread_ts:
            self.thread_ts = action.new_thread_ts
            print(f"[system] switched to thread_ts={self.thread_ts}")
        if action.stream_enabled is not None:
            self._stream_model_tokens = action.stream_enabled
            self._refresh_model_listener()
            print(f"[system] stream_model_tokens={self._stream_model_tokens}")
        if action.debug_enabled is not None:
            self._show_model_payload = action.debug_enabled
            self._refresh_model_listener()
            print(f"[system] debug_model_payload={self._show_model_payload}")
        for line in action.output_lines:
            print(line)
        return True

    def _on_model_event(self, event: str, payload: dict[str, Any]) -> None:
        if not self._stream_model_tokens and not self._show_model_payload:
            return

        if event == "model_start":
            self._active_stream_buffer = []
            if self._show_model_payload:
                print("[debug] model request")
                print("[debug] system_prompt:")
                print(self._as_text(payload.get("system_prompt")))
                print("[debug] request_payload:")
                print(self._as_text(payload.get("request_payload")))
                tools = payload.get("tools")
                if isinstance(tools, list) and tools:
                    print("[debug] tools:")
                    print(self._as_text(tools))
            return

        if event == "model_token":
            if not self._stream_model_tokens:
                return
            token = str(payload.get("token", ""))
            if token:
                if not self._stream_line_open:
                    self._print_section("Final (live)")
                    self._stream_line_open = True
                self._active_stream_buffer.append(token)
                print(token, end="", flush=True)
            return

        if event == "model_reasoning_token":
            if not self._stream_model_tokens and not self._show_model_payload:
                return
            token = str(payload.get("token", ""))
            if not token:
                return
            if not self._reasoning_line_open:
                print("- ", end="", flush=True)
                self._reasoning_line_open = True
            print(token, end="", flush=True)
            return

        if event in {"model_end", "model_error"}:
            self._last_streamed_text = "".join(self._active_stream_buffer).strip()
            self._active_stream_buffer = []
            self._close_live_lines()

    def _refresh_model_listener(self) -> None:
        self.service.set_model_event_listener(self._on_model_event)

    def _begin_task(self, raw: str) -> None:
        self._task_active = True
        self._thinking_printed = False
        self._pending_final_text = ""
        self._print_section("Task")
        print(f"- {raw}")

    def _render_runtime_event(self, event: RuntimeEvent) -> None:
        step_prefix = f"Step {event.step} · " if event.step > 0 else ""
        if event.event_type == "thinking":
            self._print_section(f"{step_prefix}Thinking")
            if event.text:
                print(f"- {event.text}")
            return

        if event.event_type == "tool_call":
            self._print_section(f"{step_prefix}Tool")
            print(
                f"- {self._format_trace_action({'action': event.action_name, 'input': event.action_input, 'blocked': event.blocked})}"
            )
            return

        if event.event_type == "tool_result":
            self._print_section(f"{step_prefix}Result")
            print(f"- {self._truncate(event.observation or event.text or '(empty)')}")
            return

        if event.event_type == "memory_compacted":
            self._print_section(f"{step_prefix}Memory")
            print(f"- {event.text or 'Compacted summary'}")
            return

        if event.event_type == "final_text":
            self._pending_final_text = event.text
            return

        if event.event_type == "run_completed":
            final_text = (event.text or self._pending_final_text).strip()
            self._print_section(f"{step_prefix}Final" if step_prefix else "Final")
            streamed = self._last_streamed_text.strip()
            if streamed and streamed == final_text:
                print("(streamed live above)")
            else:
                print(final_text)
            self._task_active = False
            self._thinking_printed = False
            self._last_streamed_text = ""
            self._pending_final_text = ""
            self._close_live_lines()
            return

    def _print_thinking(self, message: str) -> None:
        if not self._task_active:
            return
        if not self._thinking_printed:
            self._print_section("Thinking")
            self._thinking_printed = True
        print(f"- {message}")

    def _render_followup(self, reply: OutboundReply) -> None:
        note = reply.reasoning_note.strip()
        if not self._thinking_printed:
            self._print_section("Thinking")
            print(f"- {note or 'Preparing the next step.'}")
        elif note:
            print(f"- {note}")

        self._print_section("Tool")
        if reply.execution_trace:
            for item in reply.execution_trace:
                print(f"- {self._format_trace_action(item)}")
        else:
            print("- no tool call")

        self._print_section("Result")
        if reply.execution_trace:
            for item in reply.execution_trace:
                print(f"- {self._format_trace_observation(item)}")
        else:
            print("- no observation")

        self._print_section("Final")
        streamed = self._last_streamed_text.strip()
        if streamed and streamed == reply.text.strip():
            print("(streamed live above)")
        else:
            print(reply.text)
        self._task_active = False
        self._thinking_printed = False
        self._last_streamed_text = ""
        self._pending_final_text = ""

    def _close_live_lines(self) -> None:
        if self._stream_line_open:
            print()
            self._stream_line_open = False
        if self._reasoning_line_open:
            print()
            self._reasoning_line_open = False

    @staticmethod
    def _model_summary(payload: dict[str, Any]) -> str:
        provider = str(payload.get("provider") or "").strip()
        model = str(payload.get("model") or "").strip()
        target = "/".join(part for part in (provider, model) if part)
        if target:
            return f"calling model {target}"
        return "calling model"

    @staticmethod
    def _format_trace_action(item: dict[str, Any]) -> str:
        action = str(item.get("action") or "unknown").strip() or "unknown"
        input_payload = item.get("input")
        parts: list[str] = [action]
        if isinstance(input_payload, dict):
            for key in sorted(input_payload):
                parts.append(f"{key}={TeamBotCli._summarize_value(input_payload[key])}")
        if bool(item.get("blocked", False)):
            parts.append("[blocked]")
        return " ".join(parts)

    @staticmethod
    def _format_trace_observation(item: dict[str, Any]) -> str:
        observation = str(item.get("observation") or "").strip()
        if not observation:
            return "(empty)"
        return TeamBotCli._truncate(observation)

    @staticmethod
    def _summarize_value(value: Any) -> str:
        if isinstance(value, (str, int, float, bool)) or value is None:
            return TeamBotCli._truncate(str(value), limit=60)
        return TeamBotCli._truncate(json.dumps(value, ensure_ascii=False, default=str), limit=60)

    @staticmethod
    def _truncate(value: str, *, limit: int = 160) -> str:
        collapsed = " ".join(value.split())
        if len(collapsed) <= limit:
            return collapsed
        return f"{collapsed[: limit - 3]}..."

    @staticmethod
    def _print_section(title: str) -> None:
        print()
        print(title)

    @staticmethod
    def _as_text(value: Any) -> str:
        if isinstance(value, str):
            return value
        return json.dumps(value, ensure_ascii=False, indent=2, default=str)


def parse_args() -> argparse.Namespace:
    profile_descriptions = describe_profiles()
    profile_help = (
        "Override runtime tool profile for this CLI session.\n"
        f"- {TOOL_PROFILE_MINIMAL}: {profile_descriptions[TOOL_PROFILE_MINIMAL]}\n"
        f"- {TOOL_PROFILE_EXTERNAL_OPERATION}: {profile_descriptions[TOOL_PROFILE_EXTERNAL_OPERATION]}\n"
        f"- {TOOL_PROFILE_FULL}: {profile_descriptions[TOOL_PROFILE_FULL]}"
    )
    parser = argparse.ArgumentParser(
        description="TeamBot interactive CLI",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("--team-id", default="T1")
    parser.add_argument("--channel-id", default="C1")
    parser.add_argument("--thread-ts", default=None)
    parser.add_argument("--user-id", default="U1")
    parser.add_argument("--stream-model-tokens", action="store_true")
    parser.add_argument("--show-model-payload", action="store_true")
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
    cli = TeamBotCli(
        team_id=args.team_id,
        channel_id=args.channel_id,
        thread_ts=args.thread_ts,
        user_id=args.user_id,
        stream_model_tokens=args.stream_model_tokens,
        show_model_payload=args.show_model_payload,
        service=service,
    )
    asyncio.run(cli.run())


if __name__ == "__main__":
    main()
