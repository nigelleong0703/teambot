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
