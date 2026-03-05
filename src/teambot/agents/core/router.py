from __future__ import annotations

import json
from typing import Any

from ...agent_core.contracts import ModelRoleInvoker
from ...domain.models import AgentState
from ..prompts import build_system_prompt_from_working_dir
from ..providers.manager import ROLE_AGENT
from .actions import ActionRegistry

_FALLBACK_MESSAGE = "Processed."


def _finish(note: str, *, message: str | None = None) -> dict[str, Any]:
    return {
        "react_done": True,
        "reasoning_note": note,
        "skill_output": {"message": message or _FALLBACK_MESSAGE},
    }


def _select_action(
    name: str,
    note: str,
    *,
    skill_input: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "selected_skill": name,
        "skill_input": skill_input or {},
        "reasoning_note": note,
    }


def _is_tools_question(text: str) -> bool:
    normalized = text.strip().lower()
    if not normalized:
        return False
    return "tool" in normalized and any(
        token in normalized
        for token in ("what", "which", "list", "have", "available")
    )


def _deterministic_tools_message(action_registry: ActionRegistry) -> str:
    rows: list[str] = []
    for action in action_registry.list_actions():
        if action.source != "tool":
            continue
        rows.append(f"- {action.name}: {action.description}")
    if not rows:
        return "No tools are currently enabled."
    return "Enabled tools:\n" + "\n".join(rows)


def _deterministic_direct_route(state: AgentState, action_registry: ActionRegistry) -> dict[str, Any] | None:
    event_type = str(state.get("event_type", "")).strip()
    user_text = str(state.get("user_text", "")).strip()

    if event_type == "reaction_added" and action_registry.has_action("handle_reaction"):
        return _select_action("handle_reaction", "Deterministic route: reaction event")

    if user_text.startswith("/todo") and action_registry.has_action("create_task"):
        return _select_action("create_task", "Deterministic route: /todo command")

    if _is_tools_question(user_text):
        return _finish("Deterministic route: tools question", message=_deterministic_tools_message(action_registry))

    return None


def _planner_prompt(action_registry: ActionRegistry) -> str:
    actions = [
        {
            "name": action.name,
            "description": action.description,
            "source": action.source,
            "risk_level": action.risk_level,
        }
        for action in action_registry.list_actions()
    ]
    actions_json = json.dumps(actions, ensure_ascii=False)
    return (
        "You are the TeamBot planner.\n"
        "Return ONLY JSON object.\n"
        "Schema:\n"
        '{"decision":"final","message":"..."}\n'
        'or {"decision":"action","name":"<action_name>","input":{}}.\n'
        "Use only actions from the provided list.\n"
        f"Available actions: {actions_json}"
    )


def _safe_str(value: object) -> str:
    if isinstance(value, str):
        return value.strip()
    return ""


def _safe_dict(value: object) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _route_with_planner(
    *,
    state: AgentState,
    action_registry: ActionRegistry,
    planner: ModelRoleInvoker,
) -> dict[str, Any]:
    payload = {
        "event_type": state.get("event_type"),
        "user_text": state.get("user_text"),
        "reaction": state.get("reaction"),
        "last_observation": state.get("skill_output", {}),
    }
    result = planner.invoke_role_json(
        role=ROLE_AGENT,
        system_prompt=f"{build_system_prompt_from_working_dir()}\n\n{_planner_prompt(action_registry)}",
        payload=payload,
    )
    data = result.data
    decision = _safe_str(data.get("decision"))

    if decision == "action":
        action_name = _safe_str(data.get("name"))
        action_input = _safe_dict(data.get("input"))
        if action_name and action_registry.has_action(action_name):
            return _select_action(
                action_name,
                f"Planner route: action -> {action_name}",
                skill_input=action_input,
            )
        return _finish(
            "Planner selected unknown action; fallback to direct reply.",
            message="I could not map that tool call to an enabled action.",
        )

    message = _safe_str(data.get("message"))
    if decision == "final" and message:
        return _finish("Planner route: final answer", message=message)

    return _finish(
        "Planner returned invalid shape; fallback to deterministic reply.",
        message="I could not produce a valid planner output.",
    )


def _route_follow_up(
    *,
    state: AgentState,
    action_registry: ActionRegistry,
) -> dict[str, Any] | None:
    follow_up_raw = state.get("skill_output", {}).get("next_skill")
    if not follow_up_raw:
        return None

    follow_up = str(follow_up_raw).strip()
    follow_up_input = state.get("skill_output", {}).get("next_skill_input")
    if not isinstance(follow_up_input, dict):
        follow_up_input = {}

    if follow_up and action_registry.has_action(follow_up):
        return _select_action(
            follow_up,
            f"Continue with follow-up action from observation: {follow_up}",
            skill_input=follow_up_input,
        )

    return _finish(
        f"next_skill not found and cannot continue: {follow_up}",
        message="I could not continue with the requested follow-up action.",
    )


def build_reason_node(
    action_registry: ActionRegistry,
    planner: ModelRoleInvoker | None = None,
):
    def _reason(state: AgentState) -> dict[str, Any]:
        step = int(state.get("react_step", 0))
        max_steps = int(state.get("react_max_steps", 3))
        if step >= max_steps:
            return _finish(f"Reached max ReAct steps: {max_steps}")

        follow_up_route = _route_follow_up(
            state=state,
            action_registry=action_registry,
        )
        if follow_up_route is not None:
            return follow_up_route

        deterministic = _deterministic_direct_route(state, action_registry)
        if deterministic is not None:
            return deterministic

        if planner is not None and planner.has_role(ROLE_AGENT):
            try:
                return _route_with_planner(
                    state=state,
                    action_registry=action_registry,
                    planner=planner,
                )
            except Exception:
                pass

        # Safe fallback when planner is unavailable.
        return _finish(
            "No planner available; fallback final reply.",
            message=f"Acknowledged.\n\nYou said: {str(state.get('user_text', '')).strip()}",
        )

    return _reason
