from __future__ import annotations

import json
from typing import Any

from ...agent_core.contracts import ModelRoleInvoker, ModelToolSpec
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


def _planner_prompt() -> str:
    return (
        "You are TeamBot.\n"
        "You may call tools to fulfill user requests.\n"
        "Call tools when external operations are required (files, shell, browser, time).\n"
        "If no tool is needed, respond directly in plain text.\n"
        "Never invent tool names."
    )


def _safe_str(value: object) -> str:
    if isinstance(value, str):
        return value.strip()
    return ""


def _tool_specs(action_registry: ActionRegistry) -> list[ModelToolSpec]:
    specs: list[ModelToolSpec] = []
    for action in action_registry.list_actions():
        if action.source != "tool":
            continue
        schema = action.input_schema if isinstance(action.input_schema, dict) else {}
        specs.append(
            ModelToolSpec(
                name=action.name,
                description=action.description,
                input_schema=schema or {"type": "object", "properties": {}},
            )
        )
    return specs


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
    tools = _tool_specs(action_registry)
    if not tools:
        result = planner.invoke_role_text(
            role=ROLE_AGENT,
            system_prompt=f"{build_system_prompt_from_working_dir()}\n\n{_planner_prompt()}",
            user_message=json.dumps(payload, ensure_ascii=False),
        )
        message = _safe_str(result.text)
        if message:
            return _finish("Planner route: final text answer", message=message)
        return _finish(
            "Planner returned empty text and no tools were available.",
            message="I could not produce a final answer.",
        )

    result = planner.invoke_role_tools(
        role=ROLE_AGENT,
        system_prompt=f"{build_system_prompt_from_working_dir()}\n\n{_planner_prompt()}",
        payload=payload,
        tools=tools,
    )

    if result.tool_calls:
        for call in result.tool_calls:
            action_name = _safe_str(call.name)
            action_input = call.arguments if isinstance(call.arguments, dict) else {}
            if action_name and action_registry.has_action(action_name):
                return _select_action(
                    action_name,
                    f"Planner route: native tool call -> {action_name}",
                    skill_input=action_input,
                )
        return _finish(
            "Planner called unknown tool(s); fallback to direct reply.",
            message="I could not map that tool call to an enabled action.",
        )

    message = _safe_str(result.text)
    if message:
        return _finish("Planner route: final answer", message=message)

    return _finish(
        "Planner returned no text and no tool calls.",
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
