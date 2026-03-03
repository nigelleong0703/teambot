from __future__ import annotations

from ...models import AgentState

from .dynamic import load_dynamic_skills
from .registry import SkillManifest, SkillRegistry


def _general_reply(state: AgentState) -> dict[str, str]:
    text = state["user_text"].strip()
    return {
        "message": (
            "Acknowledged. The MVP currently replies using deterministic thread routing."
            f"\n\nYou said: {text}"
        ),
    }


def _create_task(state: AgentState) -> dict[str, str]:
    text = state["user_text"].strip()
    task_text = text.replace("/todo", "", 1).strip() or text
    return {
        "message": f"Task recorded: {task_text}",
    }


def _handle_reaction(state: AgentState) -> dict[str, str]:
    reaction = state.get("reaction") or ""
    mapping = {
        "white_check_mark": "Marked as completed.",
        "eyes": "Marked as in progress.",
        "x": "Marked as rejected/canceled.",
    }
    return {
        "message": mapping.get(reaction, f"Received reaction: :{reaction}:"),
    }


def build_registry(
    dynamic_skills_dir: str | None = None,
    enabled_skill_names: set[str] | None = None,
) -> SkillRegistry:
    def is_enabled(name: str) -> bool:
        return enabled_skill_names is None or name in enabled_skill_names

    registry = SkillRegistry()
    if is_enabled("general_reply"):
        registry.register(
            SkillManifest(
                name="general_reply",
                description="Default conversational response.",
            ),
            _general_reply,
        )
    if is_enabled("create_task"):
        registry.register(
            SkillManifest(
                name="create_task",
                description="Create a task from '/todo ...' user messages.",
            ),
            _create_task,
        )
    if is_enabled("handle_reaction"):
        registry.register(
            SkillManifest(
                name="handle_reaction",
                description="Convert reactions to deterministic task-state updates.",
            ),
            _handle_reaction,
        )
    if dynamic_skills_dir:
        load_dynamic_skills(registry, dynamic_skills_dir)
    return registry
