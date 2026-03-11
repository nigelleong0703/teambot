from __future__ import annotations

from teambot.agent import reason as reason_module


def test_reasoner_prompt_keeps_internal_tool_category_guidance() -> None:
    prompt = reason_module._reasoner_prompt()

    assert "files, shell, web fetch, browser, time" in prompt.lower()
    assert "prefer web_fetch" in prompt.lower()
    assert "Never invent action names." in prompt


def test_reasoner_prompt_hides_internal_implementation_details_from_users() -> None:
    prompt = reason_module._reasoner_prompt()

    assert "never expose internal tool names" in prompt.lower()
    assert "skill pack names" in prompt.lower()
    assert "user-facing capabilities only" in prompt.lower()
