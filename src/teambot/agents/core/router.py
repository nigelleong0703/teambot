from __future__ import annotations

from ...models import AgentState
from .actions import ActionRegistry


def build_reason_node(action_registry: ActionRegistry):
    manifests = action_registry.list_manifests()
    action_names = {manifest.name for manifest in manifests}
    default_action = "general_reply" if "general_reply" in action_names else ""
    if not default_action and manifests:
        default_action = manifests[0].name

    def _reason(state: AgentState) -> dict:
        step = int(state.get("react_step", 0))
        max_steps = int(state.get("react_max_steps", 3))
        if step >= max_steps:
            return {
                "react_done": True,
                "reasoning_note": f"Reached max ReAct steps: {max_steps}",
                "skill_output": {"message": "Processed."},
            }

        follow_up_skill = state.get("skill_output", {}).get("next_skill")
        if follow_up_skill:
            follow_up = str(follow_up_skill).strip()
            if follow_up and action_registry.has_action(follow_up):
                return {
                    "selected_skill": follow_up,
                    "skill_input": {},
                    "reasoning_note": (
                        f"Continue with follow-up action from observation: {follow_up}"
                    ),
                }
            if not default_action:
                return {
                    "react_done": True,
                    "reasoning_note": (
                        f"next_skill not found and no fallback action is available: {follow_up}"
                    ),
                    "skill_output": {"message": "Processed."},
                }
            return {
                "selected_skill": default_action,
                "skill_input": {},
                "reasoning_note": (
                    f"next_skill not found, fallback to {default_action}: {follow_up}"
                ),
            }

        if state.get("event_type") == "reaction_added" and action_registry.has_action(
            "handle_reaction"
        ):
            return {
                "selected_skill": "handle_reaction",
                "skill_input": {},
                "reasoning_note": "Deterministic route: reaction_added -> handle_reaction",
            }

        text = str(state.get("user_text", "")).strip().lower()
        if text.startswith("/todo") and action_registry.has_action("create_task"):
            return {
                "selected_skill": "create_task",
                "skill_input": {},
                "reasoning_note": "Deterministic route: /todo -> create_task",
            }

        if default_action:
            return {
                "selected_skill": default_action,
                "skill_input": {},
                "reasoning_note": f"Deterministic route: default -> {default_action}",
            }

        if manifests:
            first_action = manifests[0].name
            return {
                "selected_skill": first_action,
                "skill_input": {},
                "reasoning_note": f"Deterministic route: first available -> {first_action}",
            }

        return {
            "react_done": True,
            "reasoning_note": "No action is registered; finish safely.",
            "skill_output": {"message": "Processed."},
        }

    return _reason


def route_after_reason(state: AgentState) -> str:
    return "compose_reply" if state.get("react_done", False) else "act"
