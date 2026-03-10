from __future__ import annotations

from dataclasses import dataclass

from ..domain.models import ConversationTurn

_TRUNCATED_SUFFIX = "..."
_TURN_OVERHEAD_CHARS = 16


@dataclass(frozen=True)
class CharBudgetMemoryPolicy:
    recent_turn_char_budget: int = 2000
    recent_turn_max_chars: int = 500
    min_recent_turns: int = 2
    summary_max_chars: int = 4000
    summary_turn_max_chars: int = 180

    def recent_turns(
        self,
        turns: list[ConversationTurn],
        *,
        last_compacted_seq: int = 0,
    ) -> list[dict[str, str]]:
        return [
            self._render_turn(turn, max_chars=self.recent_turn_max_chars)
            for turn in self._recent_window(
                self._turns_after_boundary(turns, last_compacted_seq),
            )
        ]

    def compactable_turns(
        self,
        *,
        turns: list[ConversationTurn],
        last_compacted_seq: int,
    ) -> list[ConversationTurn]:
        uncompacted = self._turns_after_boundary(turns, last_compacted_seq)
        if not uncompacted:
            return []

        recent_window = self._recent_window(uncompacted)
        compact_count = max(0, len(uncompacted) - len(recent_window))
        return uncompacted[:compact_count]

    @staticmethod
    def _turns_after_boundary(
        turns: list[ConversationTurn],
        last_compacted_seq: int,
    ) -> list[ConversationTurn]:
        return [
            turn
            for turn in turns
            if int(turn.seq or 0) > last_compacted_seq
        ]

    def _recent_window(self, turns: list[ConversationTurn]) -> list[ConversationTurn]:
        selected: list[ConversationTurn] = []
        used_chars = 0

        for turn in reversed(turns):
            rendered = self._render_turn(turn, max_chars=self.recent_turn_max_chars)
            turn_chars = self._estimate_turn_chars(rendered)
            exceeds_budget = bool(selected) and used_chars + turn_chars > self.recent_turn_char_budget
            if exceeds_budget and len(selected) >= self.min_recent_turns:
                break
            selected.append(turn)
            used_chars += turn_chars

        return list(reversed(selected))

    def _estimate_turn_chars(self, rendered_turn: dict[str, str]) -> int:
        return (
            len(rendered_turn["role"])
            + len(rendered_turn["text"])
            + _TURN_OVERHEAD_CHARS
        )

    def truncate_summary_text(self, value: str) -> str:
        return self._truncate(value, self.summary_turn_max_chars)

    @staticmethod
    def _render_turn(turn: ConversationTurn, *, max_chars: int) -> dict[str, str]:
        return {
            "role": turn.role.strip(),
            "text": CharBudgetMemoryPolicy._truncate(turn.text.strip(), max_chars),
        }

    @staticmethod
    def _truncate(value: str, limit: int) -> str:
        collapsed = " ".join(value.split())
        if len(collapsed) <= limit:
            return collapsed
        available = max(0, limit - len(_TRUNCATED_SUFFIX))
        return f"{collapsed[:available]}{_TRUNCATED_SUFFIX}"
