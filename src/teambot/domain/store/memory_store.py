from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path

from ...runtime_paths import get_agent_store_db_path
from ..models import ConversationRecord, ConversationSummaryState, ConversationTurn, OutboundReply, ReplyTarget


def make_conversation_key(target: ReplyTarget) -> str:
    return f"{target.team_id}:{target.channel_id}:{target.thread_ts}"


class MemoryStore:
    """SQLite-backed runtime store for MVP. Replace with Postgres/Redis in production."""

    def __init__(
        self,
        history_limit: int = 30,
        db_path: str | Path | None = None,
    ) -> None:
        self._history_limit = history_limit
        self._db_path = Path(db_path) if db_path is not None else get_agent_store_db_path()
        self._db_path = self._db_path.expanduser().resolve()
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self._db_path)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._connection.execute("PRAGMA journal_mode = WAL")
        self._connection.execute("PRAGMA synchronous = NORMAL")
        self._init_schema()
        self._migrate_schema()   # ← add this line
        self._lock = asyncio.Lock()

    async def get_processed_event(self, event_id: str) -> OutboundReply | None:
        async with self._lock:
            row = self._connection.execute(
                "SELECT reply_json FROM processed_events WHERE event_id = ?",
                (event_id,),
            ).fetchone()
        if row is None:
            return None
        return OutboundReply.model_validate_json(str(row["reply_json"]))

    async def save_processed_event(self, event_id: str, reply: OutboundReply) -> None:
        async with self._lock:
            self._connection.execute(
                """
                INSERT INTO processed_events (event_id, conversation_key, reply_json)
                VALUES (?, ?, ?)
                ON CONFLICT(event_id) DO UPDATE SET
                    conversation_key = excluded.conversation_key,
                    reply_json = excluded.reply_json,
                    created_at = CURRENT_TIMESTAMP
                """,
                (
                    event_id,
                    reply.conversation_key,
                    reply.model_dump_json(),
                ),
            )
            self._connection.commit()

    async def upsert_conversation(self, target: ReplyTarget) -> ConversationRecord:
        key = make_conversation_key(target)
        async with self._lock:
            self._connection.execute(
                """
                INSERT INTO conversations (
                    conversation_key,
                    team_id,
                    channel_id,
                    thread_ts
                )
                VALUES (?, ?, ?, ?)
                ON CONFLICT(conversation_key) DO UPDATE SET
                    team_id = excluded.team_id,
                    channel_id = excluded.channel_id,
                    thread_ts = excluded.thread_ts
                """,
                (
                    key,
                    target.team_id,
                    target.channel_id,
                    target.thread_ts,
                ),
            )
            self._connection.commit()
            history = self._list_history_locked(key)
        return ConversationRecord(
            conversation_key=key,
            reply_target=target,
            history=history,
        )

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

    async def get_summary_state(self, conversation_key: str) -> ConversationSummaryState:
        async with self._lock:
            row = self._connection.execute(
                """
                SELECT rolling_summary, last_compacted_seq
                FROM conversation_state
                WHERE conversation_key = ?
                """,
                (conversation_key,),
            ).fetchone()
        if row is None:
            return ConversationSummaryState()
        return ConversationSummaryState(
            rolling_summary=str(row["rolling_summary"] or ""),
            last_compacted_seq=int(row["last_compacted_seq"] or 0),
        )

    async def save_summary_state(
        self,
        conversation_key: str,
        *,
        rolling_summary: str,
        last_compacted_seq: int,
    ) -> None:
        async with self._lock:
            self._connection.execute(
                """
                INSERT INTO conversation_state (conversation_key, rolling_summary, last_compacted_seq)
                VALUES (?, ?, ?)
                ON CONFLICT(conversation_key) DO UPDATE SET
                    rolling_summary = excluded.rolling_summary,
                    last_compacted_seq = excluded.last_compacted_seq,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    conversation_key,
                    rolling_summary,
                    last_compacted_seq,
                ),
            )
            self._connection.commit()

    async def list_conversations(self) -> list[ConversationRecord]:
        async with self._lock:
            rows = self._connection.execute(
                """
                SELECT conversation_key, team_id, channel_id, thread_ts
                FROM conversations
                ORDER BY updated_at DESC, conversation_key DESC
                """
            ).fetchall()
            return [
                ConversationRecord(
                    conversation_key=str(row["conversation_key"]),
                    reply_target=ReplyTarget(
                        team_id=str(row["team_id"]),
                        channel_id=str(row["channel_id"]),
                        thread_ts=str(row["thread_ts"]),
                    ),
                    history=self._list_history_locked(str(row["conversation_key"])),
                )
                for row in rows
            ]

    async def list_conversation_turns(self, conversation_key: str) -> list[ConversationTurn]:
        async with self._lock:
            return self._list_history_locked(conversation_key)

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
            except sqlite3.OperationalError as exc:
                raise RuntimeError("FTS5 not available in this SQLite build") from exc

    def _init_schema(self) -> None:
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                conversation_key TEXT PRIMARY KEY,
                team_id TEXT NOT NULL,
                channel_id TEXT NOT NULL,
                thread_ts TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS conversation_turns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_key TEXT NOT NULL,
                seq INTEGER NOT NULL,
                role TEXT NOT NULL,
                text TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(conversation_key) REFERENCES conversations(conversation_key) ON DELETE CASCADE
            );

            CREATE UNIQUE INDEX IF NOT EXISTS idx_conversation_turns_key_seq
            ON conversation_turns (conversation_key, seq);

            CREATE INDEX IF NOT EXISTS idx_conversation_turns_key_id
            ON conversation_turns (conversation_key, id DESC);

            CREATE TABLE IF NOT EXISTS processed_events (
                event_id TEXT PRIMARY KEY,
                conversation_key TEXT NOT NULL,
                reply_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS conversation_state (
                conversation_key TEXT PRIMARY KEY,
                rolling_summary TEXT NOT NULL DEFAULT '',
                last_compacted_seq INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(conversation_key) REFERENCES conversations(conversation_key) ON DELETE CASCADE
            );
            """
        )
        self._connection.commit()
