from __future__ import annotations

from pathlib import Path

from teambot.agent.prompts.system_prompt import build_system_prompt_from_working_dir


def test_system_prompt_loads_markdown_from_agent_home_system(
    monkeypatch,
    tmp_path: Path,
) -> None:
    agent_home = tmp_path / ".teambot" / "agents" / "prompt-agent"
    system_dir = agent_home / "system"
    system_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("AGENT_HOME", str(agent_home))
    (system_dir / "AGENTS.md").write_text("Use concise answers.", encoding="utf-8")
    (system_dir / "PROFILE.md").write_text("Call me Test Agent.", encoding="utf-8")

    prompt = build_system_prompt_from_working_dir()

    assert "# AGENTS.md" in prompt
    assert "Use concise answers." in prompt
    assert "# PROFILE.md" in prompt
    assert "Call me Test Agent." in prompt
