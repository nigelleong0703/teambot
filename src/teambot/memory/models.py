from __future__ import annotations

from dataclasses import dataclass, field

from ..domain.models import ReplyTarget


@dataclass(frozen=True)
class SessionMemoryContext:
    conversation_key: str
    reply_target: ReplyTarget
    conversation_summary: str = ""
    recent_turns: list[dict[str, str]] = field(default_factory=list)


@dataclass(frozen=True)
class SessionCompactionResult:
    compacted: bool = False
    last_compacted_seq: int = 0


@dataclass(frozen=True)
class MemoryContext:
    system_prompt_suffix: str = ""
    conversation_summary: str = ""
    recent_turns: list[dict[str, str]] = field(default_factory=list)
