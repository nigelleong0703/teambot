from __future__ import annotations

from pathlib import Path

from ..runtime_paths import get_agent_system_dir

_MEMORY_FILE_CANDIDATES = ("memory.md", "MEMORY.md")


class FileLongTermMemoryProvider:
    def __init__(self, *, system_dir: Path | None = None) -> None:
        self._system_dir = system_dir

    def build_system_prompt_suffix(self) -> str:
        content = self._load_memory_text().strip()
        if not content:
            return ""
        return f"Long-term memory:\n{content}"

    def _load_memory_text(self) -> str:
        base_dir = self._system_dir or get_agent_system_dir()
        for name in _MEMORY_FILE_CANDIDATES:
            path = base_dir / name
            if not path.exists() or not path.is_file():
                continue
            try:
                return path.read_text(encoding="utf-8")
            except OSError:
                return ""
        return ""
