from __future__ import annotations

import pytest

from teambot.domain.models import OutboundReply, ReplyTarget
from teambot.domain.store import MemoryStore
from teambot.runtime_paths import get_agent_store_db_path, get_agent_todo_path


@pytest.mark.asyncio
async def test_memory_store_persists_conversation_turns_across_instances() -> None:
    store = MemoryStore()
    target = ReplyTarget(team_id="T1", channel_id="C1", thread_ts="1.1")
    conversation = await store.upsert_conversation(target)

    await store.append_turns(
        conversation_key=conversation.conversation_key,
        user_text="hello",
        assistant_text="world",
    )

    reopened = MemoryStore()
    restored = await reopened.upsert_conversation(target)

    assert restored.history[0].role == "user"
    assert restored.history[0].text == "hello"
    assert restored.history[1].role == "assistant"
    assert restored.history[1].text == "world"


@pytest.mark.asyncio
async def test_memory_store_persists_processed_event_cache() -> None:
    store = MemoryStore()
    reply = OutboundReply(
        event_id="evt-1",
        conversation_key="T1:C1:1.1",
        reply_target=ReplyTarget(team_id="T1", channel_id="C1", thread_ts="1.1"),
        text="done",
        skill_name="",
    )

    await store.save_processed_event("evt-1", reply)

    reopened = MemoryStore()
    restored = await reopened.get_processed_event("evt-1")

    assert restored is not None
    assert restored.text == "done"
    assert restored.conversation_key == "T1:C1:1.1"


@pytest.mark.asyncio
async def test_memory_store_persists_summary_state() -> None:
    store = MemoryStore()
    target = ReplyTarget(team_id="T1", channel_id="C1", thread_ts="1.2")
    conversation = await store.upsert_conversation(target)

    await store.save_summary_state(
        conversation.conversation_key,
        rolling_summary="Earlier turns agreed to use SQLite.",
        last_compacted_seq=4,
    )

    reopened = MemoryStore()
    restored = await reopened.get_summary_state(conversation.conversation_key)

    assert restored.rolling_summary == "Earlier turns agreed to use SQLite."
    assert restored.last_compacted_seq == 4


def test_memory_store_uses_agent_home_state_database_path() -> None:
    store = MemoryStore()

    assert store._db_path == get_agent_store_db_path().resolve()
    assert store._db_path.name == "teambot.sqlite"


def test_runtime_paths_place_todo_document_under_agent_work_dir(tmp_path) -> None:
    todo_path = get_agent_todo_path(tmp_path)

    assert todo_path == (tmp_path / "work" / "todo.md").resolve()
