from __future__ import annotations

from ...domain.models import AgentState
from .registry import EventHandlerManifest, EventHandlerRegistry


def _create_task(state: AgentState) -> dict[str, str]:
    text = str(state.get("user_text", "")).strip()
    task_text = text.replace("/todo", "", 1).strip() or text
    return {"message": f"Task recorded: {task_text}"}


def _handle_reaction(state: AgentState) -> dict[str, str]:
    reaction = str(state.get("reaction") or "")
    mapping = {
        "white_check_mark": "Marked as completed.",
        "eyes": "Marked as in progress.",
        "x": "Marked as rejected/canceled.",
    }
    return {"message": mapping.get(reaction, f"Received reaction: :{reaction}:")}


def build_registry() -> EventHandlerRegistry:
    registry = EventHandlerRegistry()
    registry.register(
        EventHandlerManifest(
            name="create_task",
            description="Create a task from '/todo ...' user messages.",
        ),
        _create_task,
    )
    registry.register(
        EventHandlerManifest(
            name="handle_reaction",
            description="Convert reactions to deterministic task-state updates.",
        ),
        _handle_reaction,
    )
    return registry

