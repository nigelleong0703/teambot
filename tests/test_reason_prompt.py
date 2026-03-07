from __future__ import annotations

from teambot.agent import reason as reason_module


def test_reasoner_prompt_keeps_internal_tool_category_guidance() -> None:
    prompt = reason_module._reasoner_prompt()

    assert "files, shell, browser, time" in prompt
    assert "Never invent action names." in prompt


def test_reasoner_prompt_does_not_add_user_visibility_rule() -> None:
    prompt = reason_module._reasoner_prompt()

    assert "do not expose" not in prompt.lower()
    assert "do not reveal" not in prompt.lower()
    assert "tool list" not in prompt.lower()
