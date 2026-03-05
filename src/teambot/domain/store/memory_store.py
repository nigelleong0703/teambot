from __future__ import annotations

import asyncio
from collections import deque

from ..models import ConversationRecord, ConversationTurn, OutboundReply, ReplyTarget


def make_conversation_key(target: ReplyTarget) -> str:
    return f"{target.team_id}:{target.channel_id}:{target.thread_ts}"


class MemoryStore:
    """In-memory store for MVP. Replace with Postgres/Redis in production."""

    def __init__(self, history_limit: int = 30):
        self._history_limit = history_limit
        self._conversations: dict[str, ConversationRecord] = {}
        self._processed_events: dict[str, OutboundReply] = {}
        self._lock = asyncio.Lock()

    async def get_processed_event(self, event_id: str) -> OutboundReply | None:
        async with self._lock:
            return self._processed_events.get(event_id)

    async def save_processed_event(self, event_id: str, reply: OutboundReply) -> None:
        async with self._lock:
            self._processed_events[event_id] = reply

    async def upsert_conversation(self, target: ReplyTarget) -> ConversationRecord:
        key = make_conversation_key(target)
        async with self._lock:
            record = self._conversations.get(key)
            if record is None:
                record = ConversationRecord(conversation_key=key, reply_target=target)
                self._conversations[key] = record
            return record

    async def append_turns(
        self,
        conversation_key: str,
        user_text: str,
        assistant_text: str,
    ) -> None:
        async with self._lock:
            record = self._conversations[conversation_key]
            history = deque(record.history, maxlen=self._history_limit)
            history.append(ConversationTurn(role="user", text=user_text))
            history.append(ConversationTurn(role="assistant", text=assistant_text))
            record.history = list(history)

    async def list_conversations(self) -> list[ConversationRecord]:
        async with self._lock:
            return list(self._conversations.values())
