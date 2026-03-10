from __future__ import annotations

from dataclasses import dataclass
import json
from typing import TYPE_CHECKING, Callable, Protocol

from ..contracts.contracts import ModelRoleInvoker
from ..domain.models import ConversationTurn
from .models import SessionCompactionResult
from .policy import CharBudgetMemoryPolicy
from ..providers.registry import PROFILE_SUMMARY, candidate_profile_names

if TYPE_CHECKING:
    from ..domain.store import MemoryStore

_TRUNCATED_SUFFIX = "..."

def _truncate_text(value: str, limit: int) -> str:
    collapsed = " ".join(value.split())
    if len(collapsed) <= limit:
        return collapsed
    available = max(0, limit - len(_TRUNCATED_SUFFIX))
    return f"{collapsed[:available]}{_TRUNCATED_SUFFIX}"


class SummaryGenerator(Protocol):
    def generate(
        self,
        *,
        previous_summary: str,
        compacted_turns: list[ConversationTurn],
    ) -> str:
        ...


@dataclass(frozen=True)
class NoopSummaryGenerator:
    def generate(
        self,
        *,
        previous_summary: str,
        compacted_turns: list[ConversationTurn],
    ) -> str:
        _ = (previous_summary, compacted_turns)
        return ""


@dataclass(frozen=True)
class ProviderBackedSummaryGenerator:
    reasoner: ModelRoleInvoker | None
    max_summary_chars: int = 4000
    max_turn_text_chars: int = 180
    profile: str = PROFILE_SUMMARY

    def generate(
        self,
        *,
        previous_summary: str,
        compacted_turns: list[ConversationTurn],
    ) -> str:
        if self.reasoner is None or not _has_profile(self.reasoner, self.profile):
            return ""

        payload = {
            "previous_summary": previous_summary.strip(),
            "compacted_turns": [
                {
                    "role": turn.role,
                    "text": _truncate_text(
                        turn.text.strip(),
                        self.max_turn_text_chars,
                    ),
                }
                for turn in compacted_turns
                if turn.text.strip()
            ],
        }
        if not payload["compacted_turns"]:
            return ""

        restore_listener = self._suppress_reasoner_events()
        try:
            result = _invoke_profile_text(
                self.reasoner,
                profile=self.profile,
                system_prompt=self._system_prompt(),
                user_message=json.dumps(payload, ensure_ascii=False),
            )
        except Exception:
            return ""
        finally:
            restore_listener()

        return self._normalize_summary_text(result.text)

    def _suppress_reasoner_events(self) -> Callable[[], None]:
        set_listener = getattr(self.reasoner, "set_event_listener", None)
        if not callable(set_listener):
            return lambda: None
        previous = getattr(self.reasoner, "_event_listener", None)
        set_listener(None)
        return lambda: set_listener(previous)

    def _normalize_summary_text(self, value: str) -> str:
        collapsed = value.strip()
        if not collapsed:
            return ""
        if len(collapsed) <= self.max_summary_chars:
            return collapsed
        available = max(0, self.max_summary_chars - len(_TRUNCATED_SUFFIX))
        return f"{collapsed[:available]}{_TRUNCATED_SUFFIX}"

    @staticmethod
    def _system_prompt() -> str:
        return (
            "You are compressing session-scoped working memory for TeamBot.\n"
            "Rewrite the prior summary plus compacted turns into a concise rolling summary.\n"
            "Return plain text only, no markdown fences or JSON.\n"
            "Keep only stable context that will help the next turn: current goal, decisions, constraints, completed actions, and unresolved items.\n"
            "Do not mention that this is a summary rewrite."
        )


def _has_profile(reasoner: ModelRoleInvoker, profile: str) -> bool:
    has_profile = getattr(reasoner, "has_profile", None)
    if callable(has_profile):
        return bool(has_profile(profile))
    for candidate in candidate_profile_names(profile):
        if reasoner.has_role(candidate):
            return True
    return False


def _invoke_profile_text(
    reasoner: ModelRoleInvoker,
    *,
    profile: str,
    system_prompt: str,
    user_message: str,
):
    invoke_profile_text = getattr(reasoner, "invoke_profile_text", None)
    if callable(invoke_profile_text):
        return invoke_profile_text(
            profile=profile,
            system_prompt=system_prompt,
            user_message=user_message,
        )
    last_error: Exception | None = None
    for candidate in candidate_profile_names(profile):
        try:
            return reasoner.invoke_role_text(
                role=candidate,
                system_prompt=system_prompt,
                user_message=user_message,
            )
        except Exception as exc:  # pragma: no cover - compatibility path
            last_error = exc
    if last_error is not None:
        raise last_error
    return reasoner.invoke_role_text(
        role=profile,
        system_prompt=system_prompt,
        user_message=user_message,
    )


class RollingSummaryCompactionEngine:
    def __init__(
        self,
        *,
        policy: CharBudgetMemoryPolicy | None = None,
        summary_generator: SummaryGenerator | None = None,
    ) -> None:
        self._policy = policy or CharBudgetMemoryPolicy()
        self._summary_generator = summary_generator or NoopSummaryGenerator()

    async def maybe_compact(
        self,
        *,
        store: MemoryStore,
        conversation_key: str,
    ) -> SessionCompactionResult:
        turns = await store.list_conversation_turns(conversation_key)
        if not turns:
            return SessionCompactionResult()

        current_state = await store.get_summary_state(conversation_key)
        compactable = self._policy.compactable_turns(
            turns=turns,
            last_compacted_seq=current_state.last_compacted_seq,
        )
        if not compactable:
            return SessionCompactionResult()

        new_summary = self._summary_generator.generate(
            previous_summary=current_state.rolling_summary,
            compacted_turns=compactable,
        )
        if not new_summary.strip():
            return SessionCompactionResult()

        last_compacted_seq = int(compactable[-1].seq or current_state.last_compacted_seq)
        await store.save_summary_state(
            conversation_key,
            rolling_summary=new_summary,
            last_compacted_seq=last_compacted_seq,
        )
        return SessionCompactionResult(
            compacted=True,
            last_compacted_seq=last_compacted_seq,
        )
