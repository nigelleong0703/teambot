from __future__ import annotations

import argparse
import asyncio
import json
import time
import uuid
from typing import Any

from .agents.core.service import AgentService
from .interfaces.bootstrap import build_agent_service
from .models import InboundEvent


class TeamBotCli:
    def __init__(
        self,
        *,
        team_id: str,
        channel_id: str,
        thread_ts: str,
        user_id: str,
        stream_model_tokens: bool = False,
        show_model_payload: bool = False,
        service: AgentService | None = None,
    ) -> None:
        self.team_id = team_id
        self.channel_id = channel_id
        self.thread_ts = thread_ts
        self.user_id = user_id
        self.service = service or build_agent_service()
        self._stream_model_tokens = stream_model_tokens
        self._show_model_payload = show_model_payload
        self._stream_line_open = False
        self._reasoning_line_open = False
        if stream_model_tokens or show_model_payload:
            self.service.set_model_event_listener(self._on_model_event)

    async def run(self) -> None:
        self._print_help()
        while True:
            try:
                raw = input("you> ").strip()
            except EOFError:
                print()
                break
            except KeyboardInterrupt:
                print()
                break

            if not raw:
                continue
            if raw in {"/exit", "exit", "quit"}:
                break
            if raw == "/help":
                self._print_help()
                continue
            if raw == "/newthread":
                self.thread_ts = self._new_thread_ts()
                print(f"[system] switched to thread_ts={self.thread_ts}")
                continue
            if raw == "/stream on":
                self._stream_model_tokens = True
                self.service.set_model_event_listener(self._on_model_event)
                print("[system] stream_model_tokens=True")
                continue
            if raw == "/stream off":
                self._stream_model_tokens = False
                if self._show_model_payload:
                    self.service.set_model_event_listener(self._on_model_event)
                else:
                    self.service.set_model_event_listener(None)
                print("[system] stream_model_tokens=False")
                continue
            if raw == "/debug on":
                self._show_model_payload = True
                self.service.set_model_event_listener(self._on_model_event)
                print("[system] debug_model_payload=True")
                continue
            if raw == "/debug off":
                self._show_model_payload = False
                if self._stream_model_tokens:
                    self.service.set_model_event_listener(self._on_model_event)
                else:
                    self.service.set_model_event_listener(None)
                print("[system] debug_model_payload=False")
                continue

            event = self._build_event(raw)
            if event is None:
                continue
            reply = await self.service.process_event(event)
            if self._stream_line_open:
                print()
                self._stream_line_open = False
            print(f"bot> {reply.text}")
            print(f"[meta] skill={reply.skill_name} thread_ts={reply.reply_target.thread_ts}")

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
    def _new_thread_ts() -> str:
        now = time.time()
        return f"{int(now)}.{int((now % 1) * 1_000_000):06d}"

    @staticmethod
    def _print_help() -> None:
        print("TeamBot CLI mode")
        print("Commands:")
        print("  /help               show this help")
        print("  /exit               exit CLI")
        print("  /newthread          start a new thread id")
        print("  /stream on|off      toggle model token streaming")
        print("  /debug on|off       print prompt/payload and reasoning tokens (if available)")
        print("  /reaction <name>    send reaction_added event")
        print("Input any other text to send a message event")

    def _on_model_event(self, event: str, payload: dict[str, Any]) -> None:
        if not self._stream_model_tokens and not self._show_model_payload:
            return
        if event == "model_start":
            if self._show_model_payload:
                print("[debug] model request")
                print("[debug] system_prompt:")
                print(self._as_text(payload.get("system_prompt")))
                print("[debug] request_payload:")
                print(self._as_text(payload.get("request_payload")))
            role = payload.get("role")
            provider = payload.get("provider")
            model = payload.get("model")
            if self._stream_model_tokens:
                print(f"[stream] {role} {provider}/{model}> ", end="", flush=True)
                self._stream_line_open = True
            return
        if event == "model_token":
            if not self._stream_model_tokens:
                return
            token = str(payload.get("token", ""))
            if token:
                print(token, end="", flush=True)
            return
        if event == "model_reasoning_token":
            if not self._show_model_payload:
                return
            token = str(payload.get("token", ""))
            if not token:
                return
            if not self._reasoning_line_open:
                print("[reason] ", end="", flush=True)
                self._reasoning_line_open = True
            print(token, end="", flush=True)
            return
        if event in {"model_end", "model_error"} and self._stream_line_open:
            print()
            self._stream_line_open = False
        if event in {"model_end", "model_error"} and self._reasoning_line_open:
            print()
            self._reasoning_line_open = False

    @staticmethod
    def _as_text(value: Any) -> str:
        if isinstance(value, str):
            return value
        return json.dumps(value, ensure_ascii=False, indent=2, default=str)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="TeamBot interactive CLI")
    parser.add_argument("--team-id", default="T1")
    parser.add_argument("--channel-id", default="C1")
    parser.add_argument("--thread-ts", default="1710000000.0001")
    parser.add_argument("--user-id", default="U1")
    parser.add_argument("--stream-model-tokens", action="store_true")
    parser.add_argument("--show-model-payload", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cli = TeamBotCli(
        team_id=args.team_id,
        channel_id=args.channel_id,
        thread_ts=args.thread_ts,
        user_id=args.user_id,
        stream_model_tokens=args.stream_model_tokens,
        show_model_payload=args.show_model_payload,
        service=build_agent_service(),
    )
    asyncio.run(cli.run())


if __name__ == "__main__":
    main()
