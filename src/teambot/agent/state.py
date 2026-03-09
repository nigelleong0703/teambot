from __future__ import annotations

from ..domain.models import AgentState, InboundEvent
from ..runtime_paths import get_agent_work_dir


def build_initial_state(
    *,
    event: InboundEvent,
    conversation_key: str,
    react_max_steps: int = 3,
) -> AgentState:
    work_dir = get_agent_work_dir()
    work_dir.mkdir(parents=True, exist_ok=True)
    return {
        "conversation_key": conversation_key,
        "event_type": event.event_type,
        "user_text": event.text,
        "reaction": event.reaction,
        "runtime_working_dir": str(work_dir),
        "react_step": 0,
        "react_max_steps": react_max_steps,
        "react_done": False,
        "react_notes": [],
        "reasoning_note": "",
        "selected_action": "",
        "selected_skill": "",
        "action_input": {},
        "skill_input": {},
        "action_output": {},
        "skill_output": {},
        "execution_trace": [],
        "reply_text": "",
    }
