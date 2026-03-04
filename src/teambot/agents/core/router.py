from __future__ import annotations

from ...models import AgentState
from .actions import ActionRegistry

_FALLBACK_MESSAGE = "Processed."


def _finish(note: str) -> dict:
    return {
        "react_done": True,
        "reasoning_note": note,
        "skill_output": {"message": _FALLBACK_MESSAGE},
    }


def _select_action(name: str, note: str) -> dict:
    return {
        "selected_skill": name,
        "skill_input": {},
        "reasoning_note": note,
    }


def _resolve_default_action(action_registry: ActionRegistry) -> str:
    manifests = action_registry.list_manifests()
    action_names = {manifest.name for manifest in manifests}
    if "general_reply" in action_names:
        return "general_reply"
    if manifests:
        return manifests[0].name
    return ""


def _route_follow_up(
    *,
    state: AgentState,
    action_registry: ActionRegistry,
    default_action: str,
) -> dict | None:
    follow_up_raw = state.get("skill_output", {}).get("next_skill")
    if not follow_up_raw:
        return None

    follow_up = str(follow_up_raw).strip()
    if follow_up and action_registry.has_action(follow_up):
        return _select_action(
            follow_up,
            f"Continue with follow-up action from observation: {follow_up}",
        )

    if not default_action:
        return _finish(
            f"next_skill not found and no fallback action is available: {follow_up}"
        )
    return _select_action(
        default_action,
        f"next_skill not found, fallback to {default_action}: {follow_up}",
    )


def _route_event_or_command(state: AgentState, action_registry: ActionRegistry) -> dict | None:
    if state.get("event_type") == "reaction_added" and action_registry.has_action(
        "handle_reaction"
    ):
        return _select_action(
            "handle_reaction",
            "Deterministic route: reaction_added -> handle_reaction",
        )

    text = str(state.get("user_text", "")).strip().lower()
    if text.startswith("/todo") and action_registry.has_action("create_task"):
        return _select_action(
            "create_task",
            "Deterministic route: /todo -> create_task",
        )
    return None


def _route_default(action_registry: ActionRegistry, default_action: str) -> dict:
    if default_action:
        return _select_action(
            default_action,
            f"Deterministic route: default -> {default_action}",
        )

    manifests = action_registry.list_manifests()
    if manifests:
        first_action = manifests[0].name
        return _select_action(
            first_action,
            f"Deterministic route: first available -> {first_action}",
        )
    return _finish("No action is registered; finish safely.")


def build_reason_node(action_registry: ActionRegistry):
    default_action = _resolve_default_action(action_registry)

    def _reason(state: AgentState) -> dict:
        step = int(state.get("react_step", 0))
        max_steps = int(state.get("react_max_steps", 3))
        if step >= max_steps:
            return _finish(f"Reached max ReAct steps: {max_steps}")

        follow_up_route = _route_follow_up(
            state=state,
            action_registry=action_registry,
            default_action=default_action,
        )
        if follow_up_route is not None:
            return follow_up_route

        event_or_command_route = _route_event_or_command(state, action_registry)
        if event_or_command_route is not None:
            return event_or_command_route

        return _route_default(action_registry, default_action)

    return _reason
