from __future__ import annotations

import sqlite3

import pytest

from teambot.domain.models import ConversationTurn, ReplyTarget
from teambot.domain.store import MemoryStore
from teambot.memory import SessionMemoryManager


# ---------------------------------------------------------------------------
# Task 1: ConversationTurn token fields
# ---------------------------------------------------------------------------

def test_conversation_turn_accepts_token_fields() -> None:
    turn = ConversationTurn(role="assistant", text="hello", seq=1, input_tokens=100, output_tokens=50)
    assert turn.input_tokens == 100
    assert turn.output_tokens == 50


def test_conversation_turn_token_fields_default_to_none() -> None:
    turn = ConversationTurn(role="user", text="hi", seq=1)
    assert turn.input_tokens is None
    assert turn.output_tokens is None


# ---------------------------------------------------------------------------
# Task 2: Schema migration
# ---------------------------------------------------------------------------

def test_migration_adds_columns_to_existing_db(tmp_path) -> None:
    """Migration adds input_tokens and output_tokens to a DB that lacks them."""
    db_file = tmp_path / "old.db"

    # Build a DB with the old schema (no token columns)
    conn = sqlite3.connect(db_file)
    conn.executescript("""
        CREATE TABLE conversations (
            conversation_key TEXT PRIMARY KEY,
            team_id TEXT NOT NULL,
            channel_id TEXT NOT NULL,
            thread_ts TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE conversation_turns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_key TEXT NOT NULL,
            seq INTEGER NOT NULL,
            role TEXT NOT NULL,
            text TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE processed_events (
            event_id TEXT PRIMARY KEY,
            conversation_key TEXT NOT NULL,
            reply_json TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE conversation_state (
            conversation_key TEXT PRIMARY KEY,
            rolling_summary TEXT NOT NULL DEFAULT '',
            last_compacted_seq INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        INSERT INTO conversations (conversation_key, team_id, channel_id, thread_ts)
        VALUES ('old:key:1', 'T1', 'C1', '1.0');
        INSERT INTO conversation_turns (conversation_key, seq, role, text)
        VALUES ('old:key:1', 1, 'user', 'old message');
    """)
    conn.commit()
    conn.close()

    # Opening MemoryStore on the existing DB triggers migration
    MemoryStore(db_path=db_file)

    conn2 = sqlite3.connect(db_file)
    cols = {row[1] for row in conn2.execute("PRAGMA table_info(conversation_turns)")}
    conn2.close()
    assert "input_tokens" in cols
    assert "output_tokens" in cols


def test_migration_adds_fts_table(tmp_path) -> None:
    """Opening MemoryStore creates the turns_fts virtual table."""
    db_file = tmp_path / "fts.db"
    MemoryStore(db_path=db_file)

    conn = sqlite3.connect(db_file)
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    conn.close()
    assert "turns_fts" in tables


def test_migration_is_idempotent(tmp_path) -> None:
    """Opening MemoryStore twice on the same DB does not raise."""
    db_file = tmp_path / "idem.db"
    MemoryStore(db_path=db_file)
    MemoryStore(db_path=db_file)  # second open must not crash


# ---------------------------------------------------------------------------
# Task 3: append_turns token storage + _list_history_locked reads them back
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_append_turns_stores_token_counts(tmp_path) -> None:
    store = MemoryStore(db_path=tmp_path / "tok.db")
    target = ReplyTarget(team_id="T1", channel_id="C1", thread_ts="1.1")
    conversation = await store.upsert_conversation(target)

    await store.append_turns(
        conversation_key=conversation.conversation_key,
        user_text="hello",
        assistant_text="world",
        input_tokens=42,
        output_tokens=17,
    )

    turns = await store.list_conversation_turns(conversation.conversation_key)
    user_turn = next(t for t in turns if t.role == "user")
    assistant_turn = next(t for t in turns if t.role == "assistant")

    assert user_turn.input_tokens is None
    assert user_turn.output_tokens is None
    assert assistant_turn.input_tokens == 42
    assert assistant_turn.output_tokens == 17


@pytest.mark.asyncio
async def test_append_turns_accepts_none_tokens(tmp_path) -> None:
    """append_turns without token kwargs stores NULL — backward-compatible."""
    store = MemoryStore(db_path=tmp_path / "null_tok.db")
    target = ReplyTarget(team_id="T1", channel_id="C1", thread_ts="2.1")
    conversation = await store.upsert_conversation(target)

    await store.append_turns(
        conversation_key=conversation.conversation_key,
        user_text="hi",
        assistant_text="there",
    )

    turns = await store.list_conversation_turns(conversation.conversation_key)
    assistant_turn = next(t for t in turns if t.role == "assistant")
    assert assistant_turn.input_tokens is None
    assert assistant_turn.output_tokens is None
