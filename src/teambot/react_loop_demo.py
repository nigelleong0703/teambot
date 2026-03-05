from __future__ import annotations

import argparse
import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

from .agents.providers.manager import ROLE_AGENT
from .agents.core.state import build_initial_state
from .interfaces.bootstrap import build_agent_service
from .models import InboundEvent, ReplyTarget
from .store import make_conversation_key

EventCallback = Callable[[str, dict[str, Any]], None]


@dataclass
class TraceCollector:
    model_calls: list[dict[str, Any]] = field(default_factory=list)
    action_calls: list[dict[str, Any]] = field(default_factory=list)
    reason_calls: list[dict[str, Any]] = field(default_factory=list)

    def reset(self) -> None:
        self.model_calls.clear()
        self.action_calls.clear()
        self.reason_calls.clear()


class ReactLoopDebugRunner:
    def __init__(self, on_event: EventCallback | None = None) -> None:
        self.service = build_agent_service()
        self.trace = TraceCollector()
        self._on_event = on_event
        self._install_hooks()

    def _emit(self, kind: str, payload: dict[str, Any]) -> None:
        if self._on_event is None:
            return
        self._on_event(kind, payload)

    def _install_hooks(self) -> None:
        manager = self.service.provider_manager
        if manager is not None and manager.has_role(ROLE_AGENT):
            original_invoke_json = manager.invoke_role_json
            original_invoke_text = manager.invoke_role_text

            def traced_invoke_json(
                *,
                role: str,
                system_prompt: str,
                payload: dict[str, Any],
            ):
                call: dict[str, Any] = {
                    "role": role,
                    "system_prompt": system_prompt,
                    "payload": payload,
                }
                provider_hint = ""
                model_hint = ""
                try:
                    binding = manager.settings.get_role_binding(role)  # type: ignore[attr-defined]
                    if binding.endpoints:
                        provider_hint = binding.endpoints[0].provider
                        model_hint = binding.endpoints[0].model
                except Exception:
                    pass

                started = time.perf_counter()
                self._emit(
                    "model_start",
                    {
                        "role": role,
                        "provider": provider_hint,
                        "model": model_hint,
                    },
                )
                streamed_tokens: list[str] = []

                def on_token(token: str) -> None:
                    if not token:
                        return
                    streamed_tokens.append(token)
                    self._emit(
                        "model_token",
                        {
                            "role": role,
                            "provider": provider_hint,
                            "model": model_hint,
                            "token": token,
                        },
                    )

                try:
                    result = original_invoke_json(
                        role=role,
                        system_prompt=system_prompt,
                        payload=payload,
                        on_token=on_token,
                    )
                    duration_ms = int((time.perf_counter() - started) * 1000)
                    call.update(
                        {
                            "response": result.data,
                            "provider": result.provider,
                            "model": result.model,
                            "finish_reason": result.finish_reason,
                            "usage": result.usage,
                            "duration_ms": duration_ms,
                            "streamed_text": "".join(streamed_tokens),
                        }
                    )
                    self.trace.model_calls.append(call)
                    self._emit(
                        "model_end",
                        {
                            "role": role,
                            "provider": result.provider,
                            "model": result.model,
                            "usage": result.usage,
                            "duration_ms": duration_ms,
                        },
                    )
                    return result
                except Exception as exc:  # pragma: no cover
                    duration_ms = int((time.perf_counter() - started) * 1000)
                    call["error"] = str(exc)
                    call["duration_ms"] = duration_ms
                    self.trace.model_calls.append(call)
                    self._emit(
                        "model_error",
                        {
                            "role": role,
                            "provider": provider_hint,
                            "model": model_hint,
                            "error": str(exc),
                            "duration_ms": duration_ms,
                        },
                    )
                    raise

            def traced_invoke_text(
                *,
                role: str,
                system_prompt: str,
                user_message: str,
            ):
                call: dict[str, Any] = {
                    "role": role,
                    "system_prompt": system_prompt,
                    "user_message": user_message,
                }
                provider_hint = ""
                model_hint = ""
                try:
                    binding = manager.settings.get_role_binding(role)  # type: ignore[attr-defined]
                    if binding.endpoints:
                        provider_hint = binding.endpoints[0].provider
                        model_hint = binding.endpoints[0].model
                except Exception:
                    pass

                started = time.perf_counter()
                self._emit(
                    "model_start",
                    {
                        "role": role,
                        "provider": provider_hint,
                        "model": model_hint,
                    },
                )
                streamed_tokens: list[str] = []

                def on_token(token: str) -> None:
                    if not token:
                        return
                    streamed_tokens.append(token)
                    self._emit(
                        "model_token",
                        {
                            "role": role,
                            "provider": provider_hint,
                            "model": model_hint,
                            "token": token,
                        },
                    )

                try:
                    result = original_invoke_text(
                        role=role,
                        system_prompt=system_prompt,
                        user_message=user_message,
                        on_token=on_token,
                    )
                    duration_ms = int((time.perf_counter() - started) * 1000)
                    call.update(
                        {
                            "response_text": result.text,
                            "provider": result.provider,
                            "model": result.model,
                            "finish_reason": result.finish_reason,
                            "usage": result.usage,
                            "duration_ms": duration_ms,
                            "streamed_text": "".join(streamed_tokens),
                        }
                    )
                    self.trace.model_calls.append(call)
                    self._emit(
                        "model_end",
                        {
                            "role": role,
                            "provider": result.provider,
                            "model": result.model,
                            "usage": result.usage,
                            "duration_ms": duration_ms,
                        },
                    )
                    return result
                except Exception as exc:  # pragma: no cover
                    duration_ms = int((time.perf_counter() - started) * 1000)
                    call["error"] = str(exc)
                    call["duration_ms"] = duration_ms
                    self.trace.model_calls.append(call)
                    self._emit(
                        "model_error",
                        {
                            "role": role,
                            "provider": provider_hint,
                            "model": model_hint,
                            "error": str(exc),
                            "duration_ms": duration_ms,
                        },
                    )
                    raise

            manager.invoke_role_json = traced_invoke_json  # type: ignore[method-assign]
            manager.invoke_role_text = traced_invoke_text  # type: ignore[method-assign]

        graph = self.service.graph
        original_reason = graph.reason_node

        def traced_reason(state: dict[str, Any]) -> dict[str, Any]:
            step = int(state.get("react_step", 0))
            self._emit(
                "reason_start",
                {
                    "step": step,
                    "event_type": state.get("event_type"),
                    "selected_skill": state.get("selected_skill", ""),
                },
            )
            output = original_reason(state)
            done = bool(output.get("react_done", False))
            route = "compose_reply" if done else "act"
            call = {
                "step": step,
                "input": {
                    "event_type": state.get("event_type"),
                    "user_text": state.get("user_text"),
                    "selected_skill": state.get("selected_skill", ""),
                    "last_observation": state.get("skill_output", {}),
                },
                "output": output,
                "done": done,
                "route": route,
            }
            self.trace.reason_calls.append(call)
            self._emit(
                "reason_end",
                {
                    "step": step,
                    "done": done,
                    "route": route,
                    "selected_skill": output.get("selected_skill", ""),
                    "reasoning_note": output.get("reasoning_note", ""),
                },
            )
            return output

        graph.reason_node = traced_reason  # type: ignore[method-assign]

        plugin_host = self.service.plugin_host
        original_action_invoke = plugin_host.invoke

        def traced_action_invoke(name: str, state: dict[str, Any]) -> dict[str, Any]:
            action = plugin_host.get_action(name)
            record: dict[str, Any] = {
                "name": action.name,
                "source": action.source,
                "risk_level": action.risk_level,
                "input_state": self._state_preview(state),
            }
            started = time.perf_counter()
            self._emit(
                "action_start",
                {
                    "name": action.name,
                    "source": action.source,
                    "risk_level": action.risk_level,
                },
            )
            try:
                output = original_action_invoke(name, state)
                duration_ms = int((time.perf_counter() - started) * 1000)
                record["output"] = output
                record["duration_ms"] = duration_ms
                self.trace.action_calls.append(record)
                self._emit(
                    "action_end",
                    {
                        "name": action.name,
                        "source": action.source,
                        "risk_level": action.risk_level,
                        "duration_ms": duration_ms,
                    },
                )
                return output
            except Exception as exc:  # pragma: no cover
                duration_ms = int((time.perf_counter() - started) * 1000)
                record["error"] = str(exc)
                record["duration_ms"] = duration_ms
                self.trace.action_calls.append(record)
                self._emit(
                    "action_error",
                    {
                        "name": action.name,
                        "source": action.source,
                        "risk_level": action.risk_level,
                        "error": str(exc),
                        "duration_ms": duration_ms,
                    },
                )
                raise

        plugin_host.invoke = traced_action_invoke  # type: ignore[method-assign]

    @staticmethod
    def _state_preview(state: dict[str, Any]) -> dict[str, Any]:
        return {
            "react_step": state.get("react_step"),
            "selected_skill": state.get("selected_skill"),
            "skill_input": state.get("skill_input"),
            "skill_output": state.get("skill_output"),
            "user_text": state.get("user_text"),
            "reaction": state.get("reaction"),
        }

    def run_event(self, event: InboundEvent, react_max_steps: int) -> dict[str, Any]:
        self.trace.reset()
        started = time.perf_counter()
        self._emit(
            "run_start",
            {
                "event_type": event.event_type,
                "thread_ts": event.thread_ts,
            },
        )

        target = ReplyTarget(
            team_id=event.team_id,
            channel_id=event.channel_id,
            thread_ts=event.thread_ts,
        )
        state = build_initial_state(
            event=event,
            conversation_key=make_conversation_key(target),
            react_max_steps=react_max_steps,
        )
        final_state = self.service.graph.invoke(state)

        total_duration_ms = int((time.perf_counter() - started) * 1000)
        self._emit(
            "run_end",
            {
                "selected_skill": final_state.get("selected_skill"),
                "duration_ms": total_duration_ms,
            },
        )
        return {
            "event": event.model_dump(),
            "model_role_bound": bool(
                self.service.provider_manager
                and self.service.provider_manager.has_role(ROLE_AGENT)
            ),
            "timing": {
                "total_duration_ms": total_duration_ms,
            },
            "reason_calls": list(self.trace.reason_calls),
            "model_calls": list(self.trace.model_calls),
            "action_calls": list(self.trace.action_calls),
            "react_summary": {
                "selected_skill": final_state.get("selected_skill"),
                "reply_text": final_state.get("reply_text"),
                "react_done": final_state.get("react_done"),
                "react_step": final_state.get("react_step"),
                "reasoning_note": final_state.get("reasoning_note"),
                "react_notes": final_state.get("react_notes"),
            },
            "execution_trace": final_state.get("execution_trace"),
            "final_state": final_state,
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Interactive ReAct loop debugger with live model/tool progress."
    )
    parser.add_argument("--event-json", default="", help="Raw JSON for one InboundEvent.")
    parser.add_argument(
        "--text",
        default="",
        help="One-shot message text. If omitted, runs interactive REPL.",
    )
    parser.add_argument("--reaction", default="eyes", help="One-shot reaction name.")
    parser.add_argument(
        "--event-type",
        default="message",
        choices=["message", "reaction_added"],
        help="One-shot event type.",
    )
    parser.add_argument("--team-id", default="T1")
    parser.add_argument("--channel-id", default="C1")
    parser.add_argument("--thread-ts", default="1710000000.0001")
    parser.add_argument("--user-id", default="U1")
    parser.add_argument("--event-id", default="")
    parser.add_argument("--react-max-steps", type=int, default=3)
    parser.add_argument(
        "--view",
        choices=["summary", "full"],
        default="summary",
        help="summary=human readable, full=full JSON report",
    )
    parser.add_argument(
        "--live-events",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Print live progress events while model/tool calls are running",
    )
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def _new_thread_ts() -> str:
    now = time.time()
    return f"{int(now)}.{int((now % 1) * 1_000_000):06d}"


def _event_id(value: str) -> str:
    return value.strip() or f"demo-{uuid.uuid4().hex[:12]}"


def _build_one_shot_event(args: argparse.Namespace) -> InboundEvent:
    if args.event_json.strip():
        payload = json.loads(args.event_json)
        if args.event_id.strip():
            payload["event_id"] = args.event_id.strip()
        return InboundEvent.model_validate(payload)

    if args.event_type == "reaction_added":
        return InboundEvent(
            event_id=_event_id(args.event_id),
            event_type="reaction_added",
            team_id=args.team_id,
            channel_id=args.channel_id,
            thread_ts=args.thread_ts,
            user_id=args.user_id,
            reaction=args.reaction,
        )

    return InboundEvent(
        event_id=_event_id(args.event_id),
        event_type="message",
        team_id=args.team_id,
        channel_id=args.channel_id,
        thread_ts=args.thread_ts,
        user_id=args.user_id,
        text=args.text or "hello",
    )


def _tokens(usage: dict[str, Any]) -> int:
    total = usage.get("total_tokens")
    if isinstance(total, int):
        return total
    inp = usage.get("input_tokens", 0)
    out = usage.get("output_tokens", 0)
    return int(inp) + int(out)


def _print_summary(report: dict[str, Any]) -> None:
    summary = report.get("react_summary", {})
    print(f"bot> {summary.get('reply_text', '')}")
    print(
        "[summary]"
        f" model_role_bound={report.get('model_role_bound')}"
        f" selected_skill={summary.get('selected_skill')}"
        f" steps={summary.get('react_step')}"
        f" total_ms={report.get('timing', {}).get('total_duration_ms')}"
    )
    print(f"[summary] note={summary.get('reasoning_note', '')}")

    reason_calls = report.get("reason_calls", [])
    if not reason_calls:
        print("[summary] reason_calls=0")
    else:
        print(f"[summary] reason_calls={len(reason_calls)}")
        for idx, call in enumerate(reason_calls, start=1):
            output = call.get("output") or {}
            selected = output.get("selected_skill", "") or "-"
            done = bool(call.get("done", False))
            route = call.get("route", "")
            note = output.get("reasoning_note", "")
            print(
                f"  - {idx}. step={call.get('step')} done={done} "
                f"route={route} selected_skill={selected}"
            )
            if note:
                print(f"    note={note}")

    model_calls = report.get("model_calls", [])
    if not model_calls:
        print("[summary] model_calls=0")
    else:
        print(f"[summary] model_calls={len(model_calls)}")
        for idx, call in enumerate(model_calls, start=1):
            if call.get("error"):
                print(
                    f"  - {idx}. role={call.get('role')} ERROR after {call.get('duration_ms')}ms: "
                    f"{call.get('error')}"
                )
                continue
            usage = call.get("usage") or {}
            print(
                f"  - {idx}. role={call.get('role')} "
                f"{call.get('provider')}/{call.get('model')} "
                f"{call.get('duration_ms')}ms tokens={_tokens(usage)}"
            )

    action_calls = report.get("action_calls", [])
    if not action_calls:
        print("[summary] action_calls=0")
    else:
        print(f"[summary] action_calls={len(action_calls)}")
        for idx, call in enumerate(action_calls, start=1):
            label = f"{call.get('name')}[{call.get('source')}]"
            if call.get("error"):
                print(
                    f"  - {idx}. {label} ERROR after {call.get('duration_ms')}ms: {call.get('error')}"
                )
                continue
            print(
                f"  - {idx}. {label} {call.get('duration_ms')}ms risk={call.get('risk_level')}"
            )


def _print_report(
    report: dict[str, Any],
    *,
    view: str,
    pretty: bool,
) -> None:
    _print_summary(report)
    if view == "full":
        print(json.dumps(report, indent=2 if pretty else None, ensure_ascii=False, default=str))


def _build_live_printer(state: dict[str, Any]) -> EventCallback:
    token_stream_open = {"value": False}

    def on_event(kind: str, payload: dict[str, Any]) -> None:
        if not state.get("live_events", True):
            return
        if kind == "run_start":
            print(
                f"[live] run start event_type={payload.get('event_type')} "
                f"thread={payload.get('thread_ts')}",
                flush=True,
            )
            return
        if kind == "model_start":
            print(
                f"[live] model start role={payload.get('role')} "
                f"{payload.get('provider')}/{payload.get('model')}",
                flush=True,
            )
            print("[live] model tokens> ", end="", flush=True)
            token_stream_open["value"] = True
            return
        if kind == "reason_start":
            print(
                f"[live] reason start step={payload.get('step')} "
                f"event={payload.get('event_type')}",
                flush=True,
            )
            return
        if kind == "reason_end":
            selected = payload.get("selected_skill") or "-"
            print(
                f"[live] reason end step={payload.get('step')} "
                f"route={payload.get('route')} done={payload.get('done')} "
                f"selected_skill={selected}",
                flush=True,
            )
            note = str(payload.get("reasoning_note", "")).strip()
            if note:
                print(f"[live] reason note> {note}", flush=True)
            return
        if kind == "model_token":
            token = str(payload.get("token", ""))
            if token:
                print(token, end="", flush=True)
            return
        if kind == "model_end":
            if token_stream_open["value"]:
                print()
                token_stream_open["value"] = False
            print(
                f"[live] model end role={payload.get('role')} "
                f"{payload.get('provider')}/{payload.get('model')} "
                f"{payload.get('duration_ms')}ms tokens={_tokens(payload.get('usage') or {})}",
                flush=True,
            )
            return
        if kind == "model_error":
            if token_stream_open["value"]:
                print()
                token_stream_open["value"] = False
            print(
                f"[live] model error role={payload.get('role')} "
                f"{payload.get('duration_ms')}ms: {payload.get('error')}",
                flush=True,
            )
            return
        if kind == "action_start":
            print(
                f"[live] action start {payload.get('name')}[{payload.get('source')}] "
                f"risk={payload.get('risk_level')}",
                flush=True,
            )
            return
        if kind == "action_end":
            print(
                f"[live] action end {payload.get('name')} "
                f"{payload.get('duration_ms')}ms",
                flush=True,
            )
            return
        if kind == "action_error":
            print(
                f"[live] action error {payload.get('name')} "
                f"{payload.get('duration_ms')}ms: {payload.get('error')}",
                flush=True,
            )
            return
        if kind == "run_end":
            print(
                f"[live] run end selected_skill={payload.get('selected_skill')} "
                f"total={payload.get('duration_ms')}ms",
                flush=True,
            )

    return on_event


def _run_interactive(args: argparse.Namespace) -> None:
    thread_ts = args.thread_ts
    state = {
        "view": args.view,
        "live_events": args.live_events,
    }
    runner = ReactLoopDebugRunner(on_event=_build_live_printer(state))

    print("ReAct Loop Debug REPL")
    print(
        "Commands: /help, /newthread, /reaction <name>, /view <summary|full>, "
        "/live <on|off>, /exit"
    )
    while True:
        try:
            raw = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not raw:
            continue
        if raw in {"/exit", "exit", "quit"}:
            break
        if raw == "/help":
            print(
                "Commands: /help, /newthread, /reaction <name>, "
                "/view <summary|full>, /live <on|off>, /exit"
            )
            continue
        if raw == "/newthread":
            thread_ts = _new_thread_ts()
            print(f"[system] switched to thread_ts={thread_ts}")
            continue
        if raw.startswith("/view "):
            view = raw.split(" ", 1)[1].strip().lower()
            if view not in {"summary", "full"}:
                print("[error] view must be 'summary' or 'full'")
                continue
            state["view"] = view
            print(f"[system] view={view}")
            continue
        if raw.startswith("/live "):
            mode = raw.split(" ", 1)[1].strip().lower()
            if mode not in {"on", "off"}:
                print("[error] live mode must be 'on' or 'off'")
                continue
            state["live_events"] = mode == "on"
            print(f"[system] live_events={state['live_events']}")
            continue

        if raw.startswith("/reaction "):
            reaction = raw.split(" ", 1)[1].strip()
            if not reaction:
                print("[error] reaction name required, e.g. /reaction eyes")
                continue
            event = InboundEvent(
                event_id=_event_id(""),
                event_type="reaction_added",
                team_id=args.team_id,
                channel_id=args.channel_id,
                thread_ts=thread_ts,
                user_id=args.user_id,
                reaction=reaction,
            )
        else:
            event = InboundEvent(
                event_id=_event_id(""),
                event_type="message",
                team_id=args.team_id,
                channel_id=args.channel_id,
                thread_ts=thread_ts,
                user_id=args.user_id,
                text=raw,
            )

        report = runner.run_event(event=event, react_max_steps=args.react_max_steps)
        _print_report(
            report,
            view=state["view"],
            pretty=True,
        )


def main() -> None:
    args = parse_args()

    if not args.event_json.strip() and not args.text.strip():
        _run_interactive(args)
        return

    runner = ReactLoopDebugRunner(
        on_event=_build_live_printer({"live_events": args.live_events})
    )
    event = _build_one_shot_event(args)
    report = runner.run_event(event=event, react_max_steps=args.react_max_steps)
    _print_report(
        report,
        view=args.view,
        pretty=args.pretty,
    )


if __name__ == "__main__":
    main()
