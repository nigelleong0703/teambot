from __future__ import annotations

from pathlib import Path

from teambot.domain.models import ReplyTarget
from teambot.memory.context import MemoryContextAssembler
from teambot.memory.longterm import FileLongTermMemoryProvider
from teambot.memory.models import SessionMemoryContext


def _session_context() -> SessionMemoryContext:
    return SessionMemoryContext(
        conversation_key="T1:C1:1.1",
        reply_target=ReplyTarget(team_id="T1", channel_id="C1", thread_ts="1.1"),
        conversation_summary="Earlier turns set the repo context.",
        recent_turns=[
            {"role": "assistant", "text": "second me..."},
            {"role": "user", "text": "third"},
        ],
    )


def test_memory_context_assembler_builds_reasoner_context(tmp_path: Path) -> None:
    system_dir = tmp_path / "system"
    system_dir.mkdir(parents=True, exist_ok=True)
    (system_dir / "memory.md").write_text("- Prefer concise answers.\n", encoding="utf-8")
    assembler = MemoryContextAssembler(
        long_term_memory_provider=FileLongTermMemoryProvider(system_dir=system_dir),
    )

    context = assembler.build(session_context=_session_context())

    assert context.system_prompt_suffix.startswith("Long-term memory:")
    assert context.conversation_summary == "Earlier turns set the repo context."
    assert context.recent_turns == [
        {"role": "assistant", "text": "second me..."},
        {"role": "user", "text": "third"},
    ]


def test_file_long_term_memory_provider_skips_missing_file(tmp_path: Path) -> None:
    provider = FileLongTermMemoryProvider(system_dir=tmp_path / "system")

    assert provider.build_system_prompt_suffix() == ""
