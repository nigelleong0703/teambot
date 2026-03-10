from __future__ import annotations

import json
from typing import Any, Callable

from ..contracts.contracts import ActionPluginRegistry, ModelRoleInvoker, ModelToolSpec
from ..domain.models import AgentState
from ..providers.manager import PROFILE_AGENT
from ..providers.registry import candidate_profile_names
from ..skills.context import build_reasoner_skill_context
from .prompts import build_system_prompt_from_working_dir
from .execution import action_output_update, action_selection_update, get_action_output

_FALLBACK_MESSAGE = "Processed."


def _finish(note: str, *, message: str | None = None) -> dict[str, Any]:
    payload = {
        "react_done": True,
        "reasoning_note": note,
    }
    payload.update(action_output_update({"message": message or _FALLBACK_MESSAGE}))
    return payload


def _select_action(
    name: str,
    note: str,
    *,
    action_input: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = action_selection_update(action_name=name, action_input=action_input)
    payload["reasoning_note"] = note
    return payload


def _deterministic_direct_route(
    state: AgentState,
    action_registry: ActionPluginRegistry,
) -> dict[str, Any] | None:
    event_type = str(state.get("event_type", "")).strip()
    user_text = str(state.get("user_text", "")).strip()

    if event_type == "reaction_added" and action_registry.has_action("handle_reaction"):
        return _select_action("handle_reaction", "Deterministic route: reaction event")

    if user_text.startswith("/todo") and action_registry.has_action("create_task"):
        return _select_action("create_task", "Deterministic route: /todo command")

    return None


def _reasoner_prompt() -> str:
    return (
        "You are TeamBot.\n"
        "You may call tools to fulfill user requests.\n"
        "Call tools when external operations are required (files, shell, browser, time).\n"
        "Use loaded skill context as guidance, not as executable actions.\n"
        "Never expose internal tool names, skill pack names, action names, slash commands, or implementation details to end users.\n"
        "When users ask what you can do, answer with user-facing capabilities only.\n"
        "If no action is needed, respond directly in plain text.\n"
        "Never invent action names."
    )


def _safe_str(value: object) -> str:
    if isinstance(value, str):
        return value.strip()
    return ""


def _reasoner_system_prompt(state: AgentState) -> str:
    prompt = f"{build_system_prompt_from_working_dir()}\n\n{_reasoner_prompt()}"
    skill_context = build_reasoner_skill_context()
    if skill_context.system_prompt_suffix:
        prompt = f"{prompt}\n\n{skill_context.system_prompt_suffix}"
    memory_suffix = _safe_str(state.get("memory_system_prompt_suffix"))
    if memory_suffix:
        prompt = f"{prompt}\n\n{memory_suffix}"
    return prompt


def _reasoner_payload(state: AgentState) -> dict[str, Any]:
    payload = {
        "event_type": state.get("event_type"),
        "user_text": state.get("user_text"),
        "reaction": state.get("reaction"),
        "last_observation": get_action_output(state),
    }
    recent_turns = state.get("recent_turns", [])
    if recent_turns:
        payload["recent_turns"] = recent_turns
    conversation_summary = _safe_str(state.get("conversation_summary"))
    if conversation_summary:
        payload["conversation_summary"] = conversation_summary
    skill_context = build_reasoner_skill_context()
    if skill_context.payload_docs:
        payload["skill_docs"] = skill_context.payload_docs
    return payload


def _tool_specs(action_registry: ActionPluginRegistry) -> list[ModelToolSpec]:
    specs: list[ModelToolSpec] = []
    for action in action_registry.list_actions():
        if action.source != "tool":
            continue
        metadata = action.metadata if isinstance(action.metadata, dict) else {}
        schema = metadata.get("input_schema") if isinstance(metadata.get("input_schema"), dict) else {}
        specs.append(
            ModelToolSpec(
                name=action.name,
                description=action.description,
                input_schema=schema or {"type": "object", "properties": {}},
            )
        )
    return specs


def _has_profile(reasoner: ModelRoleInvoker, profile: str) -> bool:
    has_profile = getattr(reasoner, "has_profile", None)
    if callable(has_profile):
        return bool(has_profile(profile))
    for candidate in candidate_profile_names(profile):
        if reasoner.has_role(candidate):
            return True
    return False


def _invoke_profile_text(
    reasoner: ModelRoleInvoker,
    *,
    profile: str,
    system_prompt: str,
    user_message: str,
):
    invoke_profile_text = getattr(reasoner, "invoke_profile_text", None)
    if callable(invoke_profile_text):
        return invoke_profile_text(
            profile=profile,
            system_prompt=system_prompt,
            user_message=user_message,
        )
    last_error: Exception | None = None
    for candidate in candidate_profile_names(profile):
        try:
            return reasoner.invoke_role_text(
                role=candidate,
                system_prompt=system_prompt,
                user_message=user_message,
            )
        except Exception as exc:  # pragma: no cover - compatibility path
            last_error = exc
    if last_error is not None:
        raise last_error
    return reasoner.invoke_role_text(
        role=profile,
        system_prompt=system_prompt,
        user_message=user_message,
    )


def _invoke_profile_tools(
    reasoner: ModelRoleInvoker,
    *,
    profile: str,
    system_prompt: str,
    payload: dict[str, Any],
    tools: list[ModelToolSpec],
):
    invoke_profile_tools = getattr(reasoner, "invoke_profile_tools", None)
    if callable(invoke_profile_tools):
        return invoke_profile_tools(
            profile=profile,
            system_prompt=system_prompt,
            payload=payload,
            tools=tools,
        )
    last_error: Exception | None = None
    for candidate in candidate_profile_names(profile):
        try:
            return reasoner.invoke_role_tools(
                role=candidate,
                system_prompt=system_prompt,
                payload=payload,
                tools=tools,
            )
        except Exception as exc:  # pragma: no cover - compatibility path
            last_error = exc
    if last_error is not None:
        raise last_error
    return reasoner.invoke_role_tools(
        role=profile,
        system_prompt=system_prompt,
        payload=payload,
        tools=tools,
    )


def _route_with_reasoner(
    *,
    state: AgentState,
    action_registry: ActionPluginRegistry,
    reasoner: ModelRoleInvoker,
    runtime_event_listener: Callable[[RuntimeEvent], None] | None = None,
) -> dict[str, Any]:
    payload = _reasoner_payload(state)
    system_prompt = _reasoner_system_prompt(state)
    tools = _tool_specs(action_registry)
    if not tools:
        result = _invoke_profile_text(
            reasoner,
            profile=PROFILE_AGENT,
            system_prompt=system_prompt,
            user_message=json.dumps(payload, ensure_ascii=False),
        )
        message = _safe_str(result.text)
        if message:
            return _finish("Reasoner route: final text answer", message=message)
        return _finish(
            "Reasoner returned empty text and no tools were available.",
            message="I could not produce a final answer.",
        )

    result = _invoke_profile_tools(
        reasoner,
        profile=PROFILE_AGENT,
        system_prompt=system_prompt,
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
                    f"Reasoner route: native tool call -> {action_name}",
                    action_input=action_input,
                )
        return _finish(
            "Reasoner called unknown tool(s); fallback to direct reply.",
            message="I could not map that tool call to an enabled action.",
        )

    message = _safe_str(result.text)
    if message:
        return _finish("Reasoner route: final answer", message=message)

    return _finish(
        "Reasoner returned no text and no tool calls.",
        message="I could not produce a valid reasoner output.",
    )


def build_reason_node(
    action_registry: ActionPluginRegistry,
    reasoner: ModelRoleInvoker | None = None,
    planner: ModelRoleInvoker | None = None,
    runtime_event_listener: Callable[[RuntimeEvent], None] | None = None,
):
    selected_reasoner = reasoner or planner

    def _reason(state: AgentState) -> dict[str, Any]:
        step = int(state.get("react_step", 0))
        max_steps = int(state.get("react_max_steps", 3))
        if step >= max_steps:
            return _finish(f"Reached max ReAct steps: {max_steps}")

        deterministic = _deterministic_direct_route(state, action_registry)
        if deterministic is not None:
            return deterministic

        if selected_reasoner is not None and _has_profile(selected_reasoner, PROFILE_AGENT):
            try:
                return _route_with_reasoner(
                    state=state,
                    action_registry=action_registry,
                    reasoner=selected_reasoner,
                    runtime_event_listener=runtime_event_listener,
                )
            except Exception:
                pass

        return _finish(
            "No reasoner available; fallback final reply.",
            message=f"Acknowledged.\n\nYou said: {str(state.get('user_text', '')).strip()}",
        )

    return _reason
