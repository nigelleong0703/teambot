from __future__ import annotations

from dataclasses import dataclass

import pytest

from teambot.contracts.contracts import ModelTextInvocationResult
from teambot.domain.models import ConversationTurn, ReplyTarget
from teambot.domain.store import MemoryStore
from teambot.memory import (
    CharBudgetMemoryPolicy,
    ProviderBackedSummaryGenerator,
    SessionMemoryManager,
)


@dataclass
class _SummaryReasonerStub:
    text: str = "Goal: keep context small.\nConstraint: use SQLite."
    _event_listener: object = object()

    def has_profile(self, profile: str) -> bool:
        return profile == "summary"

    def has_role(self, role: str) -> bool:
        return role in {"summary", "summary_model"}

    def invoke_profile_text(
        self,
        *,
        profile: str,
        system_prompt: str,
        user_message: str,
    ) -> ModelTextInvocationResult:
        _ = (profile, system_prompt, user_message)
        return ModelTextInvocationResult(
            text=self.text,
            provider="stub",
            model="stub",
        )

    def invoke_role_text(self, *, role: str, system_prompt: str, user_message: str) -> ModelTextInvocationResult:
        _ = (role, system_prompt, user_message)
        return ModelTextInvocationResult(
            text=self.text,
            provider="stub",
            model="stub",
        )

    def set_event_listener(self, listener) -> None:
        self._event_listener = listener


@pytest.mark.asyncio
async def test_session_memory_manager_compacts_and_loads_recent_turns() -> None:
    store = MemoryStore(history_limit=40)
    target = ReplyTarget(team_id="T1", channel_id="C1", thread_ts="1.1")
    session_memory = SessionMemoryManager(
        store=store,
        policy=CharBudgetMemoryPolicy(
            recent_turn_char_budget=220,
            min_recent_turns=2,
        ),
        summary_generator=ProviderBackedSummaryGenerator(
            reasoner=_SummaryReasonerStub(text="Goal: user turn 7 to assistant turn 9."),
            max_summary_chars=1200,
            max_turn_text_chars=180,
        ),
    )
    conversation = await store.upsert_conversation(target)

    for index in range(10):
        await session_memory.append_turns(
            conversation_key=conversation.conversation_key,
            user_text=f"user turn {index}",
            assistant_text=f"assistant turn {index}",
        )

    summary_state = await store.get_summary_state(conversation.conversation_key)
    assert "Goal: user turn 7 to assistant turn 9." in summary_state.rolling_summary
    assert summary_state.last_compacted_seq == 14

    context = await session_memory.load_context(target)

    assert context.conversation_summary == summary_state.rolling_summary
    assert context.recent_turns[0]["text"] == "user turn 7"
    assert context.recent_turns[-1]["text"] == "assistant turn 9"


@pytest.mark.asyncio
async def test_session_memory_manager_rolls_previous_summary_forward() -> None:
    store = MemoryStore(history_limit=50)
    target = ReplyTarget(team_id="T1", channel_id="C1", thread_ts="1.2")
    conversation = await store.upsert_conversation(target)
    session_memory = SessionMemoryManager(
        store=store,
        policy=CharBudgetMemoryPolicy(
            recent_turn_char_budget=146,
            min_recent_turns=2,
        ),
        summary_generator=ProviderBackedSummaryGenerator(
            reasoner=_SummaryReasonerStub(text="Current goal: keep prior facts.\nOpen item: latest follow-up."),
            max_summary_chars=1600,
            max_turn_text_chars=180,
        ),
    )

    await store.save_summary_state(
        conversation.conversation_key,
        rolling_summary="Previous summary:\n- existing fact",
        last_compacted_seq=4,
    )
    for index in range(3, 11):
        await session_memory.append_turns(
            conversation_key=conversation.conversation_key,
            user_text=f"user follow-up {index}",
            assistant_text=f"assistant follow-up {index}",
        )

    summary_state = await store.get_summary_state(conversation.conversation_key)
    assert "Current goal: keep prior facts." in summary_state.rolling_summary
    assert summary_state.last_compacted_seq >= 12

    context = await session_memory.load_context(target)
    assert context.recent_turns[-1]["text"] == "assistant follow-up 10"


@pytest.mark.asyncio
async def test_provider_backed_summary_generator_skips_compaction_without_model() -> None:
    store = MemoryStore(history_limit=40)
    target = ReplyTarget(team_id="T1", channel_id="C1", thread_ts="1.3")
    conversation = await store.upsert_conversation(target)
    session_memory = SessionMemoryManager(
        store=store,
        policy=CharBudgetMemoryPolicy(recent_turn_char_budget=80),
        summary_generator=ProviderBackedSummaryGenerator(reasoner=None),
    )

    for index in range(4):
        await session_memory.append_turns(
            conversation_key=conversation.conversation_key,
            user_text=f"user turn {index}",
            assistant_text=f"assistant turn {index}",
        )

    summary_state = await store.get_summary_state(conversation.conversation_key)
    assert summary_state.rolling_summary == ""
    assert summary_state.last_compacted_seq == 0


def test_provider_backed_summary_generator_uses_model_output() -> None:
    generator = ProviderBackedSummaryGenerator(
        reasoner=_SummaryReasonerStub(text="Current goal: preserve context.\nDecision: summarize older turns."),
        max_summary_chars=1200,
        max_turn_text_chars=120,
    )

    summary = generator.generate(
        previous_summary="",
        compacted_turns=[],
    )

    assert summary == ""

    summary = generator.generate(
        previous_summary="Older summary",
        compacted_turns=[
            ConversationTurn(role="user", text="Need a summary", seq=1),
        ],
    )

    assert "Current goal: preserve context." in summary


def test_provider_backed_summary_generator_prompt_is_product_neutral() -> None:
    prompt = ProviderBackedSummaryGenerator._system_prompt()

    assert "TeamBot" not in prompt
    assert "session-scoped working memory" in prompt
