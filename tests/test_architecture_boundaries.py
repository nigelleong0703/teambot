from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_core_modules_do_not_import_provider_sdks() -> None:
    forbidden_tokens = ("langchain", "openai", "anthropic")
    core_dir = ROOT / "src" / "teambot" / "agents" / "core"

    for file_path in sorted(core_dir.glob("*.py")):
        content = file_path.read_text(encoding="utf-8")
        for token in forbidden_tokens:
            assert token not in content, f"{file_path} imports forbidden token: {token}"


def test_legacy_planner_and_model_adapter_modules_removed() -> None:
    planner_path = ROOT / "src" / "teambot" / "agents" / "planner.py"
    model_adapter_path = ROOT / "src" / "teambot" / "agents" / "model_adapter.py"

    assert not planner_path.exists()
    assert not model_adapter_path.exists()
