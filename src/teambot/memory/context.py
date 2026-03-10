from __future__ import annotations

from .longterm import FileLongTermMemoryProvider
from .models import MemoryContext, SessionMemoryContext


class MemoryContextAssembler:
    def __init__(
        self,
        *,
        long_term_memory_provider: FileLongTermMemoryProvider | None = None,
    ) -> None:
        self._long_term_memory_provider = long_term_memory_provider or FileLongTermMemoryProvider()

    def build(
        self,
        *,
        session_context: SessionMemoryContext,
    ) -> MemoryContext:
        return MemoryContext(
            system_prompt_suffix=self._long_term_memory_provider.build_system_prompt_suffix(),
            conversation_summary=session_context.conversation_summary.strip(),
            recent_turns=list(session_context.recent_turns),
        )
