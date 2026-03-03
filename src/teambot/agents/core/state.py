from __future__ import annotations

from ...models import AgentState, InboundEvent


def build_initial_state(
    *,
    event: InboundEvent,
    conversation_key: str,
    react_max_steps: int = 3,
) -> AgentState:
    return {
        "conversation_key": conversation_key,
        "event_type": event.event_type,
        "user_text": event.text,
        "reaction": event.reaction,
        "react_step": 0,
        "react_max_steps": react_max_steps,
        "react_done": False,
        "react_notes": [],
        "reasoning_note": "",
        "selected_skill": "",
        "skill_input": {},
        "skill_output": {},
        "execution_trace": [],
        "reply_text": "",
    }
