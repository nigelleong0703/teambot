from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_core_modules_do_not_import_provider_sdks() -> None:
    forbidden_tokens = ("langchain", "openai", "anthropic")
    core_dir = ROOT / "src" / "teambot" / "agents" / "core"

    for file_path in sorted(core_dir.glob("*.py")):
        content = file_path.read_text(encoding="utf-8")
        for token in forbidden_tokens:
            assert token not in content, f"{file_path} imports forbidden token: {token}"


def test_planner_uses_adapter_provider_surface() -> None:
    content = _read("src/teambot/agents/planner.py")
    assert "from ..adapters.providers import (" in content
    assert "from .providers.router import (" not in content
