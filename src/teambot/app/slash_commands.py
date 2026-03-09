from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable

from ..skills.manager import SkillService


@dataclass(frozen=True)
class SlashCommandSpec:
    usage: str
    description: str


@dataclass
class SlashCommandAction:
    handled: bool = False
    exit_requested: bool = False
    new_thread_ts: str | None = None
    stream_enabled: bool | None = None
    debug_enabled: bool | None = None
    output_lines: list[str] = field(default_factory=list)


def default_slash_command_specs(*, supports_debug: bool) -> list[SlashCommandSpec]:
    specs = [
        SlashCommandSpec("/help", "show this help"),
        SlashCommandSpec("/exit", "exit"),
        SlashCommandSpec("/newthread", "start a new thread id"),
        SlashCommandSpec("/stream on|off", "toggle model token streaming"),
        SlashCommandSpec("/reaction <name>", "send reaction_added event"),
        SlashCommandSpec("/skills", "list loaded builtin/global/agent skills"),
        SlashCommandSpec("/skills sync [--force]", "legacy: copy loaded skills into active dir"),
        SlashCommandSpec("/skills enable <name>", "legacy: enable one skill in active dir"),
        SlashCommandSpec("/skills disable <name>", "legacy: remove one skill from active dir"),
    ]
    if supports_debug:
        specs.insert(4, SlashCommandSpec("/debug on|off", "print prompt/payload and reasoning tokens"))
    return specs


def format_help_lines(*, supports_debug: bool) -> list[str]:
    return ["Commands:"] + [
        f"  {item.usage:<24} {item.description}"
        for item in default_slash_command_specs(supports_debug=supports_debug)
    ]


def new_thread_ts() -> str:
    now = time.time()
    return f"{int(now)}.{int((now % 1) * 1_000_000):06d}"


def list_skills_lines() -> list[str]:
    loaded = SkillService.list_available_skill_docs()
    if not loaded:
        return ["[skills] no skills discovered"]
    rows = ["[skills] loaded:"]
    for skill in loaded:
        description = skill.description.strip() or "(no description)"
        rows.append(f"- {skill.name} (source={skill.source}): {description}")
    return rows


def dispatch_slash_command(
    raw: str,
    *,
    supports_debug: bool,
    reload_runtime: Callable[[], None],
) -> SlashCommandAction:
    if raw == "/help":
        return SlashCommandAction(handled=True, output_lines=format_help_lines(supports_debug=supports_debug))
    if raw in {"/exit", "exit", "quit"}:
        return SlashCommandAction(handled=True, exit_requested=True)
    if raw == "/newthread":
        return SlashCommandAction(handled=True, new_thread_ts=new_thread_ts())
    if raw == "/stream on":
        return SlashCommandAction(handled=True, stream_enabled=True)
    if raw == "/stream off":
        return SlashCommandAction(handled=True, stream_enabled=False)
    if supports_debug and raw == "/debug on":
        return SlashCommandAction(handled=True, debug_enabled=True)
    if supports_debug and raw == "/debug off":
        return SlashCommandAction(handled=True, debug_enabled=False)
    if raw == "/skills":
        return SlashCommandAction(handled=True, output_lines=list_skills_lines())
    if raw.startswith("/skills "):
        parts = raw.split()
        if len(parts) >= 2 and parts[1] == "sync":
            force = "--force" in parts[2:]
            synced, skipped = SkillService.sync_all(force=force)
            reload_runtime()
            return SlashCommandAction(
                handled=True,
                output_lines=[f"[skills] synced={synced} skipped={skipped}"],
            )
        if len(parts) >= 3 and parts[1] == "enable":
            name = parts[2].strip()
            if not name:
                return SlashCommandAction(handled=True, output_lines=["[skills] usage: /skills enable <name>"])
            ok = SkillService.enable_skill(name, force=False)
            reload_runtime()
            return SlashCommandAction(
                handled=True,
                output_lines=[f"[skills] enabled={name} ok={ok}"],
            )
        if len(parts) >= 3 and parts[1] == "disable":
            name = parts[2].strip()
            if not name:
                return SlashCommandAction(handled=True, output_lines=["[skills] usage: /skills disable <name>"])
            ok = SkillService.disable_skill(name)
            reload_runtime()
            return SlashCommandAction(
                handled=True,
                output_lines=[f"[skills] disabled={name} ok={ok}"],
            )
        return SlashCommandAction(
            handled=True,
            output_lines=[
                "[skills] usage: /skills | /skills sync [--force] | "
                "/skills enable <name> | /skills disable <name>"
            ],
        )
    return SlashCommandAction(handled=False)
