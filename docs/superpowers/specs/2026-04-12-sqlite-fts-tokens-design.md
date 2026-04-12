# SQLite FTS + Token Tracking Design

**Date:** 2026-04-12
**Status:** Approved

## Overview

Extend the existing `MemoryStore` SQLite database with two capabilities:

1. **Token tracking** — persist `input_tokens` and `output_tokens` on each assistant turn, captured from the provider response at the end of each agent loop run.
2. **Full-text search (FTS)** — add an FTS5 virtual table mirroring `conversation_turns.text`, kept in sync via SQLite triggers, with a `search_turns(query)` method on `MemoryStore`.

No new files. No schema replacement. Additive changes only — existing rows get NULL tokens, existing queries unaffected.

## Architecture

`MemoryStore` gains two new columns on `conversation_turns`, a new FTS5 virtual table with sync triggers, and two new public methods. `AgentService` accumulates token usage from the loop result and passes it to `append_turns`. Nothing else changes.

## Components

### Schema migration (`memory_store.py:_init_schema`)

Run on startup via `_migrate_schema()` called from `__init__` after `_init_schema()`:

```python
def _migrate_schema(self) -> None:
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

    # Create FTS table + triggers if absent
    tables = {row[0] for row in self._connection.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table', 'shadow')"
    )}
    if "turns_fts" not in tables:
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

    self._connection.commit()
```

FTS5 content tables do not store their own copy of text — they reference `conversation_turns` directly. Triggers keep the FTS index in sync on insert, delete, and update.

### Token columns

`conversation_turns` gains two nullable `INTEGER` columns:
- `input_tokens` — number of prompt tokens sent to the model (set only on assistant turns)
- `output_tokens` — number of completion tokens returned (set only on assistant turns)
- User turns always have `NULL` for both columns

### `append_turns` signature change (`memory_store.py`)

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
```

The existing `executemany` insert is split into two separate `execute` calls so the assistant row can receive token values:

```python
# user turn — no tokens
self._connection.execute(
    "INSERT INTO conversation_turns (conversation_key, seq, role, text) VALUES (?, ?, ?, ?)",
    (conversation_key, next_seq, "user", user_text),
)
# assistant turn — with optional tokens
self._connection.execute(
    """
    INSERT INTO conversation_turns (conversation_key, seq, role, text, input_tokens, output_tokens)
    VALUES (?, ?, ?, ?, ?, ?)
    """,
    (conversation_key, next_seq + 1, "assistant", assistant_text, input_tokens, output_tokens),
)
```

### `search_turns` method (`memory_store.py`)

```python
async def search_turns(
    self,
    query: str,
    *,
    limit: int = 10,
) -> list[ConversationTurn]:
```

- Empty `query` (after strip) returns `[]` immediately with no DB hit.
- Uses FTS5 `MATCH` with `bm25` ranking:

```python
rows = self._connection.execute(
    """
    SELECT ct.seq, ct.role, ct.text, ct.conversation_key
    FROM turns_fts
    JOIN conversation_turns ct ON ct.id = turns_fts.rowid
    WHERE turns_fts MATCH ?
    ORDER BY bm25(turns_fts)
    LIMIT ?
    """,
    (query, limit),
).fetchall()
```

Returns `list[ConversationTurn]` (existing model, seq + role + text).

### `ConversationTurn` model update (`domain/models.py`)

Add two optional fields (both default to `None` — backward compatible):

```python
class ConversationTurn(BaseModel):
    role: Literal["user", "assistant"]
    text: str
    seq: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
```

### Token data flow (`agent/service.py`)

`AgentLoop.run()` returns `(final_text, updated_messages)`. The final provider result (with `usage`) is available as the return value of `provider_manager.invoke_profile_chat()` inside the loop — but it is not currently surfaced to callers.

**Change to `AgentLoop.run()`**: accumulate token usage across all steps, return total as third element:

```python
def run(...) -> tuple[str, list[dict[str, Any]], dict[str, int]]:
```

The returned `usage` dict has keys `input_tokens` and `output_tokens`, summed across all loop steps. Zero if provider returns no usage.

**Change to `AgentService`**: unpack usage and pass to `append_turns`:

```python
final_text, _, usage = self._agent.run_loop(...)
await self.session_memory.append_turns(
    conversation_key=conversation_key,
    user_text=user_text,
    assistant_text=final_text,
    input_tokens=usage.get("input_tokens"),
    output_tokens=usage.get("output_tokens"),
)
```

`SessionMemoryManager.append_turns` is a thin pass-through to `MemoryStore.append_turns` — it forwards the token kwargs.

`_list_history_locked` is updated to read `input_tokens` and `output_tokens` from the result rows and populate `ConversationTurn`.

### `SessionMemoryManager.append_turns` (`memory/session.py`)

Pass through token kwargs:

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
```

## Data Flow

```
AgentLoop.run() → (final_text, messages, usage)
    usage = {"input_tokens": N, "output_tokens": M}
        ↓
AgentService.stream_event / process_event
    append_turns(..., input_tokens=N, output_tokens=M)
        ↓
SessionMemoryManager.append_turns (pass-through)
        ↓
MemoryStore.append_turns
    INSERT assistant turn with input_tokens=N, output_tokens=M
    FTS trigger fires → turns_fts updated automatically
```

## Error Handling

- **FTS5 not available**: `_migrate_schema` raises `RuntimeError("FTS5 not available in this SQLite build")` if `CREATE VIRTUAL TABLE ... USING fts5` fails. Python's bundled `sqlite3` has FTS5 since 3.8; this is a safety net only.
- **Empty search query**: `search_turns("")` returns `[]` immediately.
- **FTS syntax error** (malformed query): `search_turns` propagates the `sqlite3.OperationalError` to the caller — no silent failure.
- **Existing rows**: token columns are `NULL` for all pre-migration turns. FTS index is empty for pre-migration rows (FTS5 content tables with `content=` only index rows inserted after trigger creation; a one-time rebuild can be triggered with `INSERT INTO turns_fts(turns_fts) VALUES('rebuild')` if needed — out of scope for this spec).

## Files Changed

- `src/teambot/domain/models.py` — add `input_tokens`, `output_tokens` to `ConversationTurn`
- `src/teambot/domain/store/memory_store.py` — `_migrate_schema`, update `append_turns`, update `_list_history_locked`, add `search_turns`
- `src/teambot/memory/session.py` — forward token kwargs through `append_turns`
- `src/teambot/agent/loop.py` — accumulate and return usage dict as third return value
- `src/teambot/agent/runtime.py` — propagate third return value from `AgentLoop.run()`
- `src/teambot/agent/service.py` — unpack usage, pass to `append_turns` in both `process_event` and `stream_event`

## Testing

- `test_append_turns_stores_token_counts` — assistant turn has tokens, user turn has NULL
- `test_search_turns_finds_matching_text` — insert turns, FTS query returns relevant ones
- `test_search_turns_empty_query_returns_empty` — guard case
- `test_fts_stays_in_sync_after_turn_deleted` — delete a turn, verify it no longer appears in search
- `test_migration_adds_columns_to_existing_db` — open a DB without columns, run migration, verify columns exist and existing rows have NULL tokens
- `test_agent_loop_returns_usage` — mock provider returns usage, verify loop accumulates and returns it
- `test_agent_service_persists_token_counts` — end-to-end: mock loop returns usage, verify stored turn has token counts

## Out of Scope

- USD cost calculation
- Per-conversation FTS filtering
- FTS index rebuild for pre-migration rows
- Using FTS results to inject context into agent prompts
