from __future__ import annotations

from ..domain.models import ReplyTarget
from ..domain.store import MemoryStore
from .compaction import ProviderBackedSummaryGenerator, RollingSummaryCompactionEngine, SummaryGenerator
from .models import SessionCompactionResult, SessionMemoryContext
from .policy import CharBudgetMemoryPolicy


class SessionMemoryManager:
    def __init__(
        self,
        *,
        store: MemoryStore,
        policy: CharBudgetMemoryPolicy | None = None,
        summary_generator: SummaryGenerator | None = None,
    ) -> None:
        self._store = store
        self._policy = policy or CharBudgetMemoryPolicy()
        generator = summary_generator or ProviderBackedSummaryGenerator(
            reasoner=None,
            max_summary_chars=self._policy.summary_max_chars,
            max_turn_text_chars=self._policy.summary_turn_max_chars,
        )
        self._compaction_engine = RollingSummaryCompactionEngine(
            policy=self._policy,
            summary_generator=generator,
        )

    async def load_context(self, reply_target: ReplyTarget) -> SessionMemoryContext:
        conversation = await self._store.upsert_conversation(reply_target)
        summary_state = await self._store.get_summary_state(conversation.conversation_key)
        return SessionMemoryContext(
            conversation_key=conversation.conversation_key,
            reply_target=conversation.reply_target,
            conversation_summary=summary_state.rolling_summary.strip(),
            recent_turns=self._policy.recent_turns(
                conversation.history,
                last_compacted_seq=summary_state.last_compacted_seq,
            ),
        )

    async def append_turns(
        self,
        *,
        conversation_key: str,
        user_text: str,
        assistant_text: str,
    ) -> SessionCompactionResult:
        await self._store.append_turns(
            conversation_key=conversation_key,
            user_text=user_text,
            assistant_text=assistant_text,
        )
        return await self._compaction_engine.maybe_compact(
            store=self._store,
            conversation_key=conversation_key,
        )
