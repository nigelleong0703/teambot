from __future__ import annotations

from ..domain.models import AgentState, InboundEvent
from ..memory.models import MemoryContext
from ..runtime_paths import get_agent_work_dir


def build_initial_state(
    *,
    event: InboundEvent,
    conversation_key: str,
    memory_context: MemoryContext | None = None,
    react_max_steps: int = 3,
) -> AgentState:
    work_dir = get_agent_work_dir()
    work_dir.mkdir(parents=True, exist_ok=True)
    context = memory_context or MemoryContext()
    return {
        "conversation_key": conversation_key,
        "recent_turns": list(context.recent_turns),
        "conversation_summary": context.conversation_summary,
        "memory_system_prompt_suffix": context.system_prompt_suffix,
        "event_type": event.event_type,
        "user_text": event.text,
        "reaction": event.reaction,
        "runtime_working_dir": str(work_dir),
        "react_step": 0,
        "react_max_steps": react_max_steps,
        "react_done": False,
        "react_notes": [],
        "reasoning_note": "",
        "active_skill_names": [],
        "active_skill_docs": [],
        "selected_action": "",
        "selected_skill": "",
        "action_input": {},
        "skill_input": {},
        "action_output": {},
        "skill_output": {},
        "execution_trace": [],
        "reply_text": "",
    }
