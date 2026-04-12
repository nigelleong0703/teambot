# SQLite FTS + Token Tracking Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `MemoryStore` with token tracking on conversation turns and FTS5 full-text search, wiring token counts through AgentLoop → TeamBotRuntime → AgentService → SessionMemoryManager → MemoryStore.

**Architecture:** Additive schema migration adds two nullable `INTEGER` columns and an FTS5 virtual table with sync triggers to the existing `conversation_turns` table. `AgentLoop.run()` accumulates token usage across steps and returns it as a third tuple element. This flows up through `TeamBotRuntime.run_loop()`, `AgentService`, and `SessionMemoryManager.append_turns()` into `MemoryStore.append_turns()`. No existing rows or queries are broken — new columns default to `NULL`.

**Tech Stack:** Python 3.11+, SQLite built-in FTS5, `sqlite3` stdlib, Pydantic v2, pytest, pytest-asyncio

---

## Files changed

| File | Change |
|------|--------|
| `src/teambot/domain/models.py` | Add `input_tokens`, `output_tokens` fields to `ConversationTurn` |
| `src/teambot/domain/store/memory_store.py` | Add `_migrate_schema`, call it in `__init__`, update `append_turns`, `_list_history_locked`, add `search_turns` |
| `src/teambot/memory/session.py` | Add `input_tokens`/`output_tokens` kwargs to `append_turns` and pass through to store |
| `src/teambot/agent/loop.py` | Accumulate usage in `run()`, return 3-tuple |
| `src/teambot/agent/runtime.py` | Update `run_loop()` return type to 3-tuple; `None`-loop fallback returns `{}` |
| `src/teambot/agent/service.py` | Unpack 3-tuple in both `process_event` and `stream_event`, pass tokens to `append_turns` |
| `tests/test_sqlite_fts_tokens.py` | New test file (8 tests) |

---

## Chunk 1: Data layer — ConversationTurn model and MemoryStore

### Task 1: ConversationTurn — add token fields

**Files:**
- Modify: `src/teambot/domain/models.py:34-38`
- Create: `tests/test_sqlite_fts_tokens.py`

- [ ] **Step 1: Create test file with failing tests**

Create `tests/test_sqlite_fts_tokens.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_sqlite_fts_tokens.py::test_conversation_turn_accepts_token_fields tests/test_sqlite_fts_tokens.py::test_conversation_turn_token_fields_default_to_none -v
```

Expected: FAIL — `ConversationTurn() got unexpected keyword argument 'input_tokens'`

- [ ] **Step 3: Add token fields to ConversationTurn**

In `src/teambot/domain/models.py`, replace the `ConversationTurn` class (currently lines 34–38):

```python
class ConversationTurn(BaseModel):
    role: Literal["user", "assistant"]
    text: str
    seq: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/test_sqlite_fts_tokens.py::test_conversation_turn_accepts_token_fields tests/test_sqlite_fts_tokens.py::test_conversation_turn_token_fields_default_to_none -v
```

Expected: PASS (2 tests)

- [ ] **Step 5: Run full suite — verify no regressions**

```
pytest --tb=short -q
```

Expected: all previously passing tests still pass

- [ ] **Step 6: Commit**

```bash
git add src/teambot/domain/models.py tests/test_sqlite_fts_tokens.py
git commit -m "feat: add input_tokens/output_tokens fields to ConversationTurn"
```

---

### Task 2: MemoryStore — schema migration

**Files:**
- Modify: `src/teambot/domain/store/memory_store.py`
- Modify: `tests/test_sqlite_fts_tokens.py`

This task adds `_migrate_schema()` and calls it from `__init__`. Migration is idempotent — safe to run on every startup.

- [ ] **Step 1: Write failing tests**

Append to `tests/test_sqlite_fts_tokens.py`:

```python

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
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_sqlite_fts_tokens.py::test_migration_adds_columns_to_existing_db tests/test_sqlite_fts_tokens.py::test_migration_adds_fts_table tests/test_sqlite_fts_tokens.py::test_migration_is_idempotent -v
```

Expected: FAIL — `MemoryStore` has no `_migrate_schema` method; columns and FTS table absent

- [ ] **Step 3: Add `_migrate_schema` and call it in `__init__`**

In `src/teambot/domain/store/memory_store.py`:

**3a.** In `__init__`, add the `_migrate_schema()` call immediately after `_init_schema()` (line 32) and before `self._lock`:

```python
        self._init_schema()
        self._migrate_schema()   # ← add this line
        self._lock = asyncio.Lock()
```

**3b.** Add the `_migrate_schema` method after `_init_schema`. Add it as a new method directly after the closing of `_init_schema` (after line 277):

```python
    def _migrate_schema(self) -> None:
        """Additive migrations — safe to run on every startup."""
        # Add token columns if absent
        cols = {row[1] for row in self._connection.execute("PRAGMA table_info(conversation_turns)")}
        if "input_tokens" not in cols:
            self._connection.execute(
                "ALTER TABLE conversation_turns ADD COLUMN input_tokens INTEGER"
            )
        if "output_tokens" not in cols:
            self._connection.execute(
                "ALTER TABLE conversation_turns ADD COLUMN output_tokens INTEGER"
            )
        self._connection.commit()

        # Create FTS table + sync triggers if absent
        tables = {
            row[0]
            for row in self._connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        if "turns_fts" not in tables:
            try:
                self._connection.executescript("""
                    CREATE VIRTUAL TABLE turns_fts USING fts5(
                        text,
                        content='conversation_turns',
                        content_rowid='id'
                    );

                    CREATE TRIGGER turns_fts_insert AFTER INSERT ON conversation_turns BEGIN
                        INSERT INTO turns_fts(rowid, text) VALUES (new.id, new.text);
                    END;

                    CREATE TRIGGER turns_fts_delete AFTER DELETE ON conversation_turns BEGIN
                        INSERT INTO turns_fts(turns_fts, rowid, text) VALUES ('delete', old.id, old.text);
                    END;

                    CREATE TRIGGER turns_fts_update AFTER UPDATE ON conversation_turns BEGIN
                        INSERT INTO turns_fts(turns_fts, rowid, text) VALUES ('delete', old.id, old.text);
                        INSERT INTO turns_fts(rowid, text) VALUES (new.id, new.text);
                    END;
                """)
            except Exception as exc:
                raise RuntimeError("FTS5 not available in this SQLite build") from exc
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/test_sqlite_fts_tokens.py::test_migration_adds_columns_to_existing_db tests/test_sqlite_fts_tokens.py::test_migration_adds_fts_table tests/test_sqlite_fts_tokens.py::test_migration_is_idempotent -v
```

Expected: PASS (3 tests)

- [ ] **Step 5: Run full suite — verify no regressions**

```
pytest --tb=short -q
```

Expected: all previously passing tests still pass

- [ ] **Step 6: Commit**

```bash
git add src/teambot/domain/store/memory_store.py tests/test_sqlite_fts_tokens.py
git commit -m "feat: add _migrate_schema with token columns and FTS5 virtual table"
```

---

### Task 3: MemoryStore — update `append_turns` and `_list_history_locked`

**Files:**
- Modify: `src/teambot/domain/store/memory_store.py`
- Modify: `tests/test_sqlite_fts_tokens.py`

Split the `executemany` into two `execute` calls so the assistant row can carry token counts. Update the SELECT to include the new columns.

- [ ] **Step 1: Write failing tests**

Append to `tests/test_sqlite_fts_tokens.py`:

```python

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
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_sqlite_fts_tokens.py::test_append_turns_stores_token_counts tests/test_sqlite_fts_tokens.py::test_append_turns_accepts_none_tokens -v
```

Expected: FAIL — `append_turns() got unexpected keyword argument 'input_tokens'`

- [ ] **Step 3: Update `append_turns` signature and body**

In `src/teambot/domain/store/memory_store.py`, replace the entire `append_turns` method (lines 96–144):

```python
    async def append_turns(
        self,
        conversation_key: str,
        user_text: str,
        assistant_text: str,
        *,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
    ) -> None:
        async with self._lock:
            row = self._connection.execute(
                "SELECT COALESCE(MAX(seq), 0) AS max_seq FROM conversation_turns WHERE conversation_key = ?",
                (conversation_key,),
            ).fetchone()
            next_seq = int(row["max_seq"]) + 1 if row is not None else 1
            # user turn — no tokens
            self._connection.execute(
                "INSERT INTO conversation_turns (conversation_key, seq, role, text) VALUES (?, ?, ?, ?)",
                (conversation_key, next_seq, "user", user_text),
            )
            # assistant turn — with optional tokens
            self._connection.execute(
                """
                INSERT INTO conversation_turns
                    (conversation_key, seq, role, text, input_tokens, output_tokens)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (conversation_key, next_seq + 1, "assistant", assistant_text, input_tokens, output_tokens),
            )
            self._connection.execute(
                """
                DELETE FROM conversation_turns
                WHERE conversation_key = ?
                  AND id NOT IN (
                      SELECT id
                      FROM conversation_turns
                      WHERE conversation_key = ?
                      ORDER BY seq DESC
                      LIMIT ?
                  )
                """,
                (
                    conversation_key,
                    conversation_key,
                    self._history_limit,
                ),
            )
            self._connection.execute(
                """
                UPDATE conversations
                SET updated_at = CURRENT_TIMESTAMP
                WHERE conversation_key = ?
                """,
                (conversation_key,),
            )
            self._connection.commit()
```

- [ ] **Step 4: Update `_list_history_locked` to include token columns**

In `src/teambot/domain/store/memory_store.py`, replace the `_list_history_locked` method (lines 214–231):

```python
    def _list_history_locked(self, conversation_key: str) -> list[ConversationTurn]:
        rows = self._connection.execute(
            """
            SELECT seq, role, text, input_tokens, output_tokens
            FROM conversation_turns
            WHERE conversation_key = ?
            ORDER BY seq ASC
            """,
            (conversation_key,),
        ).fetchall()
        return [
            ConversationTurn(
                seq=int(row["seq"]),
                role=str(row["role"]),
                text=str(row["text"]),
                input_tokens=row["input_tokens"],
                output_tokens=row["output_tokens"],
            )
            for row in rows
        ]
```

- [ ] **Step 5: Run tests to verify they pass**

```
pytest tests/test_sqlite_fts_tokens.py::test_append_turns_stores_token_counts tests/test_sqlite_fts_tokens.py::test_append_turns_accepts_none_tokens -v
```

Expected: PASS (2 tests)

- [ ] **Step 6: Run full suite — verify no regressions**

```
pytest --tb=short -q
```

Expected: all previously passing tests still pass (existing `test_memory_compaction.py` calls `append_turns` without token kwargs — the new default `None` keeps them compatible)

- [ ] **Step 7: Commit**

```bash
git add src/teambot/domain/store/memory_store.py tests/test_sqlite_fts_tokens.py
git commit -m "feat: store token counts on assistant turns in MemoryStore"
```

---

### Task 4: MemoryStore — add `search_turns`

**Files:**
- Modify: `src/teambot/domain/store/memory_store.py`
- Modify: `tests/test_sqlite_fts_tokens.py`

FTS5's `bm25()` returns negative scores — more negative = better match. `ORDER BY bm25(turns_fts)` ascending puts best results first.

- [ ] **Step 1: Write failing tests**

Append to `tests/test_sqlite_fts_tokens.py`:

```python

# ---------------------------------------------------------------------------
# Task 4: search_turns
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_search_turns_finds_matching_text(tmp_path) -> None:
    store = MemoryStore(db_path=tmp_path / "search.db")
    target_a = ReplyTarget(team_id="T1", channel_id="C1", thread_ts="3.1")
    target_b = ReplyTarget(team_id="T1", channel_id="C1", thread_ts="3.2")
    conv_a = await store.upsert_conversation(target_a)
    conv_b = await store.upsert_conversation(target_b)

    await store.append_turns(
        conversation_key=conv_a.conversation_key,
        user_text="tell me about python decorators",
        assistant_text="Python decorators wrap functions to add behaviour.",
    )
    await store.append_turns(
        conversation_key=conv_b.conversation_key,
        user_text="what is a database index",
        assistant_text="An index speeds up query lookups.",
    )

    results = await store.search_turns("python decorators")
    texts = [r.text for r in results]
    assert any("decorator" in t.lower() for t in texts)
    assert not any("index speeds" in t for t in texts)


@pytest.mark.asyncio
async def test_search_turns_empty_query_returns_empty(tmp_path) -> None:
    store = MemoryStore(db_path=tmp_path / "empty.db")
    target = ReplyTarget(team_id="T1", channel_id="C1", thread_ts="4.1")
    conv = await store.upsert_conversation(target)
    await store.append_turns(
        conversation_key=conv.conversation_key,
        user_text="hello",
        assistant_text="world",
    )

    assert await store.search_turns("") == []
    assert await store.search_turns("   ") == []


@pytest.mark.asyncio
async def test_fts_stays_in_sync_after_turn_deleted(tmp_path) -> None:
    """turns_fts_delete trigger fires on direct DELETE — turn vanishes from FTS."""
    store = MemoryStore(db_path=tmp_path / "del_sync.db")
    target = ReplyTarget(team_id="T1", channel_id="C1", thread_ts="5.1")
    conv = await store.upsert_conversation(target)

    await store.append_turns(
        conversation_key=conv.conversation_key,
        user_text="unique phrase xylophone kazoo",
        assistant_text="I heard you say xylophone kazoo.",
    )

    # Confirm it is findable before deletion
    results = await store.search_turns("xylophone kazoo")
    assert len(results) > 0

    # Directly delete the rows — this must fire the turns_fts_delete trigger
    store._connection.execute(
        "DELETE FROM conversation_turns WHERE conversation_key = ?",
        (conv.conversation_key,),
    )
    store._connection.commit()

    # FTS index must be clean after deletion
    results = await store.search_turns("xylophone kazoo")
    assert results == []


@pytest.mark.asyncio
async def test_fts_stays_in_sync_after_history_trim(tmp_path) -> None:
    """Rows removed by the history-limit DELETE also disappear from FTS results."""
    store = MemoryStore(db_path=tmp_path / "trim.db", history_limit=2)
    target = ReplyTarget(team_id="T1", channel_id="C1", thread_ts="5.2")
    conv = await store.upsert_conversation(target)

    # First turn — will be trimmed when history_limit=2 is hit
    await store.append_turns(
        conversation_key=conv.conversation_key,
        user_text="unique phrase xylophone kazoo",
        assistant_text="I heard you say xylophone kazoo.",
    )
    # Second turn — pushes first pair beyond the limit (2 rows kept)
    await store.append_turns(
        conversation_key=conv.conversation_key,
        user_text="something else entirely",
        assistant_text="Sure, something else.",
    )

    results = await store.search_turns("xylophone kazoo")
    assert results == []
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_sqlite_fts_tokens.py::test_search_turns_finds_matching_text tests/test_sqlite_fts_tokens.py::test_search_turns_empty_query_returns_empty tests/test_sqlite_fts_tokens.py::test_fts_stays_in_sync_after_turn_deleted tests/test_sqlite_fts_tokens.py::test_fts_stays_in_sync_after_history_trim -v
```

Expected: FAIL — `MemoryStore has no attribute 'search_turns'`

- [ ] **Step 3: Add `search_turns` method**

In `src/teambot/domain/store/memory_store.py`, add `search_turns` after `list_conversation_turns` (after line 212):

```python
    async def search_turns(self, query: str, *, limit: int = 10) -> list[ConversationTurn]:
        """Full-text search over all conversation turns using FTS5."""
        if not query.strip():
            return []
        async with self._lock:
            rows = self._connection.execute(
                """
                SELECT ct.seq, ct.role, ct.text, ct.input_tokens, ct.output_tokens
                FROM turns_fts
                JOIN conversation_turns ct ON ct.id = turns_fts.rowid
                WHERE turns_fts MATCH ?
                ORDER BY bm25(turns_fts)
                LIMIT ?
                """,
                (query, limit),
            ).fetchall()
        return [
            ConversationTurn(
                seq=int(row["seq"]),
                role=str(row["role"]),
                text=str(row["text"]),
                input_tokens=row["input_tokens"],
                output_tokens=row["output_tokens"],
            )
            for row in rows
        ]
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/test_sqlite_fts_tokens.py::test_search_turns_finds_matching_text tests/test_sqlite_fts_tokens.py::test_search_turns_empty_query_returns_empty tests/test_sqlite_fts_tokens.py::test_fts_stays_in_sync_after_turn_deleted tests/test_sqlite_fts_tokens.py::test_fts_stays_in_sync_after_history_trim -v
```

Expected: PASS (3 tests)

- [ ] **Step 5: Run full suite — verify no regressions**

```
pytest --tb=short -q
```

Expected: all previously passing tests still pass

- [ ] **Step 6: Commit**

```bash
git add src/teambot/domain/store/memory_store.py tests/test_sqlite_fts_tokens.py
git commit -m "feat: add search_turns FTS5 method to MemoryStore"
```

---

## Chunk 2: Agent pipeline — usage propagation

### Task 5: AgentLoop + TeamBotRuntime — return token usage

**Files:**
- Modify: `src/teambot/agent/loop.py`
- Modify: `src/teambot/agent/runtime.py`
- Modify: `tests/test_sqlite_fts_tokens.py`

`AgentLoop.run()` returns `tuple[str, list[dict], dict[str, int]]`. `TeamBotRuntime.run_loop()` propagates the same 3-tuple; the `None`-loop fallback returns `{}`.

- [ ] **Step 1: Write failing tests**

Append to `tests/test_sqlite_fts_tokens.py`:

```python

# ---------------------------------------------------------------------------
# Task 5: AgentLoop + TeamBotRuntime usage accumulation
# ---------------------------------------------------------------------------
from dataclasses import dataclass, field as dc_field
from typing import Any

from teambot.contracts.contracts import ModelToolCall, ModelToolInvocationResult
from teambot.agent.loop import AgentLoop
from teambot.agent.runtime import TeamBotRuntime
from teambot.actions.tools.registry import ToolManifest, ToolRegistry


@dataclass
class _StubProviderManager:
    """Minimal stub — returns pre-loaded responses in order."""
    _responses: list[ModelToolInvocationResult] = dc_field(default_factory=list)

    def invoke_profile_chat(self, *, profile, system_prompt, messages, tools=None, on_token=None):
        return self._responses.pop(0)


def test_agent_loop_returns_usage() -> None:
    pm = _StubProviderManager(_responses=[
        ModelToolInvocationResult(
            text="final answer",
            tool_calls=[],
            provider="stub",
            model="stub",
            usage={"input_tokens": 42, "output_tokens": 17},
        )
    ])
    loop = AgentLoop(tool_registry=ToolRegistry(), provider_manager=pm)

    result = loop.run(
        messages=[{"role": "user", "content": "hi"}],
        system_prompt="test",
    )

    final_text, _messages, usage = result
    assert final_text == "final answer"
    assert usage["input_tokens"] == 42
    assert usage["output_tokens"] == 17


def test_agent_loop_accumulates_usage_across_steps() -> None:
    tool_registry = ToolRegistry()
    tool_registry.register(
        ToolManifest(name="mytool", description="test tool"),
        lambda _state: {"message": "tool output"},
    )

    pm = _StubProviderManager(_responses=[
        ModelToolInvocationResult(
            text="",
            tool_calls=[ModelToolCall(name="mytool", arguments={}, call_id="c1")],
            provider="stub",
            model="stub",
            usage={"input_tokens": 100, "output_tokens": 10},
        ),
        ModelToolInvocationResult(
            text="done",
            tool_calls=[],
            provider="stub",
            model="stub",
            usage={"input_tokens": 50, "output_tokens": 25},
        ),
    ])

    loop = AgentLoop(tool_registry=tool_registry, provider_manager=pm)
    _, _, usage = loop.run(
        messages=[{"role": "user", "content": "use the tool"}],
        system_prompt="test",
    )

    assert usage["input_tokens"] == 150
    assert usage["output_tokens"] == 35


def test_agent_loop_none_provider_returns_empty_usage() -> None:
    runtime = TeamBotRuntime.__new__(TeamBotRuntime)
    runtime.loop = None

    _text, _messages, usage = runtime.run_loop(
        messages=[],
        system_prompt="test",
    )
    assert usage == {}
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_sqlite_fts_tokens.py::test_agent_loop_returns_usage tests/test_sqlite_fts_tokens.py::test_agent_loop_accumulates_usage_across_steps tests/test_sqlite_fts_tokens.py::test_agent_loop_none_provider_returns_empty_usage -v
```

Expected: FAIL — `loop.run()` returns a 2-tuple; `runtime.run_loop()` has no 3-tuple

- [ ] **Step 3: Update `AgentLoop.run()` to accumulate and return usage**

In `src/teambot/agent/loop.py`, make these changes:

**3a.** Update the return type annotation on line 47:

```python
    ) -> tuple[str, list[dict[str, Any]], dict[str, int]]:
```

**3b.** Add `total_input` and `total_output` accumulators right after `messages = list(messages)` (after line 53):

```python
        messages = list(messages)
        tools = self._tool_specs()
        total_input = 0
        total_output = 0
```

**3c.** After the `result = self.provider_manager.invoke_profile_chat(...)` call (after line 63), add accumulation:

```python
            result = self.provider_manager.invoke_profile_chat(
                profile=PROFILE_AGENT,
                system_prompt=system_prompt,
                messages=messages,
                tools=tools if tools else None,
                on_token=on_token,
            )
            total_input += result.usage.get("input_tokens", 0)
            total_output += result.usage.get("output_tokens", 0)
```

**3d.** Update the final-text return (line 128) to include usage:

```python
                return final_text, messages, {"input_tokens": total_input, "output_tokens": total_output}
```

**3e.** Update the max-steps return (line 132) to include usage:

```python
        messages.append({"role": "assistant", "content": _FALLBACK_TEXT})
        return _FALLBACK_TEXT, messages, {"input_tokens": total_input, "output_tokens": total_output}
```

- [ ] **Step 4: Update `TeamBotRuntime.run_loop()` to return 3-tuple**

In `src/teambot/agent/runtime.py`, update the method at lines 99–119:

```python
    def run_loop(
        self,
        *,
        messages: list[dict],
        system_prompt: str,
        conversation_key: str = "",
        working_dir: str = "",
        on_token: Callable[[str], None] | None = None,
        on_event: Callable[[RuntimeEvent], None] | None = None,
    ) -> tuple[str, list[dict], dict[str, int]]:
        """Run the stateless tool-calling loop with a full messages list."""
        if self.loop is None:
            return "No provider configured.", messages, {}
        return self.loop.run(
            messages=messages,
            system_prompt=system_prompt,
            conversation_key=conversation_key,
            working_dir=working_dir,
            on_token=on_token,
            on_event=on_event,
        )
```

- [ ] **Step 5: Run tests to verify they pass**

```
pytest tests/test_sqlite_fts_tokens.py::test_agent_loop_returns_usage tests/test_sqlite_fts_tokens.py::test_agent_loop_accumulates_usage_across_steps tests/test_sqlite_fts_tokens.py::test_agent_loop_none_provider_returns_empty_usage -v
```

Expected: PASS (3 tests)

- [ ] **Step 6: Run full suite — verify no regressions**

```
pytest --tb=short -q
```

Expected: all previously passing tests still pass. (No other code calls `run_loop()` or `loop.run()` directly in the codebase apart from `AgentService`, which will be updated in Task 6.)

- [ ] **Step 7: Commit**

```bash
git add src/teambot/agent/loop.py src/teambot/agent/runtime.py tests/test_sqlite_fts_tokens.py
git commit -m "feat: accumulate and return token usage in AgentLoop and TeamBotRuntime"
```

---

### Task 6: SessionMemoryManager + AgentService — wire tokens end-to-end

**Files:**
- Modify: `src/teambot/memory/session.py`
- Modify: `src/teambot/agent/service.py`
- Modify: `tests/test_sqlite_fts_tokens.py`

`SessionMemoryManager.append_turns` gains `input_tokens`/`output_tokens` kwargs and passes them to the store. Both `AgentService.process_event` and `AgentService.stream_event` unpack the 3-tuple and pass tokens through.

- [ ] **Step 1: Write failing tests**

Append to `tests/test_sqlite_fts_tokens.py`:

```python

# ---------------------------------------------------------------------------
# Task 6: SessionMemoryManager + AgentService end-to-end token persistence
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_session_memory_manager_forwards_token_counts(tmp_path) -> None:
    store = MemoryStore(db_path=tmp_path / "session.db")
    target = ReplyTarget(team_id="T1", channel_id="C1", thread_ts="6.1")
    session_memory = SessionMemoryManager(store=store)
    conversation = await store.upsert_conversation(target)

    await session_memory.append_turns(
        conversation_key=conversation.conversation_key,
        user_text="hello",
        assistant_text="world",
        input_tokens=100,
        output_tokens=50,
    )

    turns = await store.list_conversation_turns(conversation.conversation_key)
    assistant_turn = next(t for t in turns if t.role == "assistant")
    assert assistant_turn.input_tokens == 100
    assert assistant_turn.output_tokens == 50
```

- [ ] **Step 2: Run test to verify it fails**

```
pytest tests/test_sqlite_fts_tokens.py::test_session_memory_manager_forwards_token_counts -v
```

Expected: FAIL — `SessionMemoryManager.append_turns() got unexpected keyword argument 'input_tokens'`

- [ ] **Step 3: Update `SessionMemoryManager.append_turns`**

In `src/teambot/memory/session.py`, replace the `append_turns` method (lines 43–58):

```python
    async def append_turns(
        self,
        conversation_key: str,
        user_text: str,
        assistant_text: str,
        *,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
    ) -> SessionCompactionResult:
        await self._store.append_turns(
            conversation_key=conversation_key,
            user_text=user_text,
            assistant_text=assistant_text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        return await self._compaction_engine.maybe_compact(
            store=self._store,
            conversation_key=conversation_key,
        )
```

- [ ] **Step 4: Run test to verify it passes**

```
pytest tests/test_sqlite_fts_tokens.py::test_session_memory_manager_forwards_token_counts -v
```

Expected: PASS

- [ ] **Step 5: Update `AgentService.process_event` to unpack 3-tuple**

In `src/teambot/agent/service.py`, update `process_event` (line 137 area). Replace:

```python
        final_text, _ = self._agent.run_loop(
            messages=messages,
            system_prompt=system_prompt,
            conversation_key=conversation_key,
        )
```

with:

```python
        final_text, _, usage = self._agent.run_loop(
            messages=messages,
            system_prompt=system_prompt,
            conversation_key=conversation_key,
        )
```

And update the `append_turns` call (line 153 area). Replace:

```python
        await self.session_memory.append_turns(
            conversation_key=conversation_key,
            user_text=user_text,
            assistant_text=final_text,
        )
```

with:

```python
        await self.session_memory.append_turns(
            conversation_key=conversation_key,
            user_text=user_text,
            assistant_text=final_text,
            input_tokens=usage.get("input_tokens"),
            output_tokens=usage.get("output_tokens"),
        )
```

- [ ] **Step 6: Update `AgentService.stream_event` to unpack 3-tuple**

In `src/teambot/agent/service.py`, inside the `_run_and_store` async function in `stream_event` (line 205 area). Replace:

```python
                final_text, _ = await asyncio.to_thread(
                    self._agent.run_loop,
                    messages=messages,
                    system_prompt=system_prompt,
                    conversation_key=conversation_key,
                    on_token=_on_token,
                    on_event=_on_event,
                )
```

with:

```python
                final_text, _, usage = await asyncio.to_thread(
                    self._agent.run_loop,
                    messages=messages,
                    system_prompt=system_prompt,
                    conversation_key=conversation_key,
                    on_token=_on_token,
                    on_event=_on_event,
                )
```

And update the `append_turns` call (line 222 area). Replace:

```python
                compaction = await self.session_memory.append_turns(
                    conversation_key=conversation_key,
                    user_text=user_text,
                    assistant_text=final_text,
                )
```

with:

```python
                compaction = await self.session_memory.append_turns(
                    conversation_key=conversation_key,
                    user_text=user_text,
                    assistant_text=final_text,
                    input_tokens=usage.get("input_tokens"),
                    output_tokens=usage.get("output_tokens"),
                )
```

- [ ] **Step 7: Add `test_agent_service_persists_token_counts`**

Append to `tests/test_sqlite_fts_tokens.py`:

```python

# ---------------------------------------------------------------------------
# Task 6 (cont.): AgentService end-to-end — process_event persists token counts
# ---------------------------------------------------------------------------
from unittest.mock import patch

from teambot.agent.service import AgentService
from teambot.domain.models import InboundEvent


@pytest.mark.asyncio
async def test_agent_service_persists_token_counts(tmp_path) -> None:
    """process_event unpacks run_loop 3-tuple and stores token counts."""
    service = AgentService()
    # Redirect store to isolated tmp DB so we don't pollute the real agent store
    service.store = MemoryStore(db_path=tmp_path / "svc.db")
    service.session_memory = service._build_session_memory_manager()

    with patch.object(
        service._agent,
        "run_loop",
        return_value=("response text", [], {"input_tokens": 42, "output_tokens": 17}),
    ):
        event = InboundEvent(
            event_id="evt-svc-1",
            team_id="T1",
            channel_id="C1",
            thread_ts="9.1",
            user_id="U1",
            text="hello",
        )
        await service.process_event(event)

    turns = await service.store.list_conversation_turns("T1:C1:9.1")
    assistant_turn = next(t for t in turns if t.role == "assistant")
    assert assistant_turn.input_tokens == 42
    assert assistant_turn.output_tokens == 17
```

- [ ] **Step 8: Run all new tests**

```
pytest tests/test_sqlite_fts_tokens.py -v
```

Expected: PASS (all tests in the file)

- [ ] **Step 9: Run full suite — final check**

```
pytest --tb=short -q
```

Expected: all tests pass, 0 failures

- [ ] **Step 10: Commit**

```bash
git add src/teambot/memory/session.py src/teambot/agent/service.py tests/test_sqlite_fts_tokens.py
git commit -m "feat: wire token counts end-to-end from AgentService to MemoryStore"
```

