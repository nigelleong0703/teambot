from __future__ import annotations

from ...models import AgentState
from .system_prompt import build_system_prompt_from_working_dir


def general_reply_system_prompt() -> str:
    base_prompt = build_system_prompt_from_working_dir()
    return (
        f"{base_prompt}\n\n"
        "# Runtime Reply Rules\n"
        "- Respond directly to the latest user message.\n"
        "- Keep replies concise, practical, and natural.\n"
        "- Follow the user's language by default.\n"
        "- Do not expose internal tool/runtime details."
    )


def build_general_reply_user_message(state: AgentState) -> str:
    user_text = str(state.get("user_text", "")).strip()
    reaction = state.get("reaction")
    event_type = state.get("event_type")
    return (
        "Latest event context:\n"
        f"- event_type: {event_type}\n"
        f"- reaction: {reaction}\n"
        "\n"
        "Latest user message:\n"
        f"{user_text}"
    )
