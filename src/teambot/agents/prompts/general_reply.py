from __future__ import annotations

from typing import Any

from ...models import AgentState


def general_reply_system_prompt() -> str:
    return (
        "You are TeamBot's message tool. "
        "Return a single JSON object only. No markdown.\n"
        "Schema: {\n"
        '  "message": string\n'
        "}\n"
        "Rules:\n"
        "- Keep message concise, practical, and user-facing.\n"
        "- Do not include JSON outside the object.\n"
        "- Do not include tool/planner internals."
    )


def build_general_reply_payload(state: AgentState) -> dict[str, Any]:
    return {
        "event_type": state.get("event_type"),
        "user_text": state.get("user_text"),
        "reaction": state.get("reaction"),
        "conversation_key": state.get("conversation_key"),
        "react_step": state.get("react_step"),
        "last_observation": state.get("skill_output", {}),
    }
