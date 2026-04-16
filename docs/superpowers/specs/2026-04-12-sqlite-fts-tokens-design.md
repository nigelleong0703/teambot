# SQLite FTS + Token Tracking Design

**Date:** 2026-04-12
**Status:** Approved

## Overview

Extend the existing `MemoryStore` SQLite database with two capabilities:

1. **Token tracking** — persist `input_tokens` and `output_tokens` on each assistant turn, captured from the provider response at the end of each agent loop run.
2. **Full-text search (FTS)** — add an FTS5 virtual table mirroring `conversation_turns.text`, kept in sync via SQLite triggers, with a `search_turns(query)` method on `MemoryStore`.

No new files. No schema replacement. Additive changes only — existing rows get NULL tokens, existing queries unaffected.

## Architecture

`MemoryStore` gains two new columns on `conversation_turns`, a new FTS5 virtual table with sync triggers, and two new public methods. `AgentLoop.run()` returns usage totals as a third element. `AgentService` unpacks those totals and passes them to `append_turns`. Nothing else changes.

## Components

### Schema migration (`memory_store.py`)

`__init__` calls `_migrate_schema()` immediately after `_init_schema()`:

```python
def __init__(self, ...) -> None:
    ...
    self._init_schema()
    self._migrate_schema()   # ← add this line
    self._lock = asyncio.Lock()
```

`_migrate_schema` runs additive migrations idempotently on every startup:

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
    self._connection.commit()

    # Create FTS table + triggers if absent
    tables = {row[0] for row in self._connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
    )}
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

FTS5 content tables do not store their own copy of text — they reference `conversation_turns` directly via `content=`. Triggers keep the FTS index in sync on insert, delete, and update. Note: the history-limit DELETE in `append_turns` (which trims old rows beyond `_history_limit`) also fires `turns_fts_delete` for each removed row, keeping the FTS index clean automatically.

### Token columns

`conversation_turns` gains two nullable `INTEGER` columns:
- `input_tokens` — prompt tokens sent to the model (set only on assistant turns)
- `output_tokens` — completion tokens returned (set only on assistant turns)
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

### `_list_history_locked` update (`memory_store.py`)

Updated SELECT to fetch token fields and populate `ConversationTurn`:

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
- Uses FTS5 `MATCH` with `bm25` ranking. FTS5's `bm25()` returns negative scores — more negative means a better match — so `ORDER BY bm25(turns_fts)` (ascending, the default) correctly returns the best matches first.

```python
async def search_turns(self, query: str, *, limit: int = 10) -> list[ConversationTurn]:
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

### Token data flow (`agent/loop.py` and `agent/runtime.py`)

**`AgentLoop.run()`** — accumulate usage across all steps and return as third element:

```python
def run(
    self,
    *,
    messages: list[dict[str, Any]],
    system_prompt: str,
    conversation_key: str = "",
    working_dir: str = "",
    on_token: Callable[[str], None] | None = None,
    on_event: Callable[[RuntimeEvent], None] | None = None,
) -> tuple[str, list[dict[str, Any]], dict[str, int]]:
```

Inside the loop, accumulate usage from each step:

```python
total_input = 0
total_output = 0

for step in range(1, self.max_steps + 1):
    result = self.provider_manager.invoke_profile_chat(...)
    total_input += result.usage.get("input_tokens", 0)
    total_output += result.usage.get("output_tokens", 0)
    ...

# On final text return:
usage = {"input_tokens": total_input, "output_tokens": total_output}
return final_text, messages, usage

# On max steps hit:
return _FALLBACK_TEXT, messages, {"input_tokens": total_input, "output_tokens": total_output}
```

Both `native.py` provider clients already normalise usage keys to `input_tokens`/`output_tokens` (Anthropic via `getattr(usage_obj, "input_tokens", 0)`, OpenAI via mapping `prompt_tokens` → `input_tokens`). So `result.usage.get("input_tokens", 0)` is safe for all supported providers.

**`TeamBotRuntime.run_loop()`** — update return type and handle the `None`-loop fallback:

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

### `AgentService` update (`agent/service.py`)

Both `process_event` and `stream_event` unpack the 3-tuple and pass tokens to `append_turns`:

```python
# process_event (sync path):
final_text, _, usage = self._agent.run_loop(...)

# stream_event (async path):
final_text, _, usage = await asyncio.to_thread(self._agent.run_loop, ...)

# Both paths:
await self.session_memory.append_turns(
    conversation_key=conversation_key,
    user_text=user_text,
    assistant_text=final_text,
    input_tokens=usage.get("input_tokens"),
    output_tokens=usage.get("output_tokens"),
)
```

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
TeamBotRuntime.run_loop() — propagates 3-tuple
        ↓
AgentService.stream_event / process_event
    append_turns(..., input_tokens=N, output_tokens=M)
        ↓
SessionMemoryManager.append_turns (pass-through)
        ↓
MemoryStore.append_turns
    INSERT user turn (no tokens)
    INSERT assistant turn with input_tokens=N, output_tokens=M
    turns_fts_insert trigger fires for each → FTS index updated
    History-limit DELETE fires turns_fts_delete for removed rows → FTS index stays clean
```

## Error Handling

- **FTS5 not available**: `_migrate_schema` raises `RuntimeError("FTS5 not available in this SQLite build")` at startup. Python's bundled `sqlite3` has FTS5 since 3.8; this is a safety net only.
- **Empty search query**: `search_turns("")` returns `[]` immediately.
- **FTS syntax error** (malformed query): `search_turns` propagates the `sqlite3.OperationalError` — no silent failure.
- **Existing rows**: token columns are `NULL` for all pre-migration turns. FTS index is empty for pre-migration rows (FTS5 content tables with `content=` only index rows inserted after trigger creation; a one-time rebuild can be triggered with `INSERT INTO turns_fts(turns_fts) VALUES('rebuild')` if needed — out of scope).
- **No provider (loop is None)**: `run_loop` returns `{}` for usage; `append_turns` receives `None` for both token fields — stored as `NULL`, safe.

## Files Changed

- `src/teambot/domain/models.py` — add `input_tokens`, `output_tokens` to `ConversationTurn`
- `src/teambot/domain/store/memory_store.py` — add `_migrate_schema`, call it in `__init__`, update `append_turns`, update `_list_history_locked`, add `search_turns`
- `src/teambot/memory/session.py` — forward token kwargs through `append_turns`
- `src/teambot/agent/loop.py` — accumulate and return usage as third tuple element
- `src/teambot/agent/runtime.py` — update `run_loop` return type; return `{}` from the `None`-loop fallback
- `src/teambot/agent/service.py` — unpack 3-tuple usage, pass tokens to `append_turns` in both `process_event` and `stream_event`

## Testing

- `test_append_turns_stores_token_counts` — assistant turn has tokens; verify `list_conversation_turns` reads them back; user turn has NULL
- `test_search_turns_finds_matching_text` — insert turns across two conversations, FTS query returns relevant ones
- `test_search_turns_empty_query_returns_empty` — guard case
- `test_fts_stays_in_sync_after_turn_deleted` — delete a turn, verify it no longer appears in search results
- `test_migration_adds_columns_to_existing_db` — open a DB without token columns, run migration, verify columns exist and existing rows have NULL tokens
- `test_agent_loop_returns_usage` — mock provider returns usage, verify loop accumulates across steps and returns summed 3-tuple
- `test_agent_loop_none_provider_returns_empty_usage` — `run_loop` with `loop=None` returns `{}` as usage
- `test_agent_service_persists_token_counts` — end-to-end: mock loop returns usage, verify stored turn has token counts read back via `list_conversation_turns`

## Out of Scope

- USD cost calculation
- Per-conversation FTS filtering
- FTS index rebuild for pre-migration rows
- Using FTS results to inject context into agent prompts
