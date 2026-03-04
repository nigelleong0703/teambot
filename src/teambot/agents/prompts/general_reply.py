from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .system_prompt import build_system_prompt_from_working_dir


@dataclass(frozen=True)
class GeneralReplyPromptBundle:
    system_prompt: str
    user_message: str


def _general_reply_system_prompt() -> str:
    base_prompt = build_system_prompt_from_working_dir()
    return (
        f"{base_prompt}\n\n"
        "# Runtime Reply Rules\n"
        "- Respond directly to the latest user message.\n"
        "- Keep replies concise, practical, and natural.\n"
        "- Follow the user's language by default.\n"
        "- Do not expose internal tool/runtime details."
    )


def _general_reply_user_message(state: Mapping[str, object]) -> str:
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


def build_general_reply_prompt_bundle(
    state: Mapping[str, object],
) -> GeneralReplyPromptBundle:
    return GeneralReplyPromptBundle(
        system_prompt=_general_reply_system_prompt(),
        user_message=_general_reply_user_message(state),
    )
