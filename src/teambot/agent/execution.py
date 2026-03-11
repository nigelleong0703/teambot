from __future__ import annotations

from typing import Any, Callable
from typing import TYPE_CHECKING

from ..contracts.contracts import ActionPluginRegistry
from ..domain.models import AgentState, RuntimeEvent
from .policy import ExecutionPolicyGate

_DEFAULT_REPLY = "Processed."


def get_selected_action(state: AgentState) -> str:
    selected = state.get("selected_action")
    if isinstance(selected, str) and selected.strip():
        return selected.strip()
    legacy = state.get("selected_skill")
    if isinstance(legacy, str):
        return legacy.strip()
    return ""


def get_action_input(state: AgentState) -> dict[str, Any]:
    payload = state.get("action_input")
    if isinstance(payload, dict):
        return payload
    legacy = state.get("skill_input")
    if isinstance(legacy, dict):
        return legacy
    return {}


def get_action_output(state: AgentState) -> dict[str, Any]:
    output = state.get("action_output")
    if isinstance(output, dict):
        return output
    legacy = state.get("skill_output")
    if isinstance(legacy, dict):
        return legacy
    return {}


def action_selection_update(
    *,
    action_name: str,
    action_input: dict[str, Any] | None = None,
) -> dict[str, Any]:
    resolved_input = action_input or {}
    return {
        "selected_action": action_name,
        "selected_skill": action_name,
        "action_input": resolved_input,
        "skill_input": resolved_input,
    }


def action_output_update(output: dict[str, Any]) -> dict[str, Any]:
    return {
        "action_output": output,
        "skill_output": output,
    }


def _blocked_action_output(action_name: str, reason: str) -> dict[str, object]:
    return {
        "message": reason or f"Action blocked: {action_name}",
        "blocked": True,
    }


def _is_observation_done(step: int, max_steps: int) -> bool:
    return step >= max_steps


def build_act_node(action_registry: ActionPluginRegistry, policy_gate: ExecutionPolicyGate):
    def _act(state: AgentState) -> dict:
        action_name = get_selected_action(state)
        action = action_registry.get_action(action_name)
        decision = policy_gate.check(action.name, action.risk_level)
        if not decision.allowed:
            output = _blocked_action_output(action_name, decision.reason or "")
        else:
            output = action_registry.invoke(action_name, state)
        if isinstance(output, dict):
            state_update = output.get("_state_update")
            visible_output = {k: v for k, v in output.items() if k != "_state_update"}
        else:
            state_update = None
            visible_output = output
        updates = action_output_update(visible_output)
        if isinstance(state_update, dict):
            updates.update(state_update)
        return updates

    return _act


def observe_node(
    state: AgentState,
    runtime_event_listener: Callable[[RuntimeEvent], None] | None = None,
) -> dict:
    step = int(state.get("react_step", 0)) + 1
    max_steps = int(state.get("react_max_steps", 3))
    output = get_action_output(state)
    done = _is_observation_done(step, max_steps)

    notes = list(state.get("react_notes", []))
    trace = list(state.get("execution_trace", []))
    message = str(output.get("message", ""))
    selected_action = get_selected_action(state)
    selected_action_input = get_action_input(state)
    blocked = bool(output.get("blocked", False))
    notes.append(f"step={step} action={selected_action} observation={message}")
    trace.append(
        {
            "step": step,
            "action": selected_action,
            "input": selected_action_input,
            "blocked": blocked,
            "observation": message,
        }
    )
    if runtime_event_listener is not None and selected_action:
        runtime_event_listener(
            RuntimeEvent(
                run_id=str(state.get("conversation_key", "")),
                step=step,
                event_type="tool_result",
                action_name=selected_action,
                action_input=selected_action_input,
                observation=message,
                blocked=blocked,
            )
        )
    return {
        "react_step": step,
        "react_done": done,
        "react_notes": notes,
        "execution_trace": trace,
    }


def compose_reply_node(
    state: AgentState,
    runtime_event_listener: Callable[[RuntimeEvent], None] | None = None,
) -> dict:
    message = str(get_action_output(state).get("message", ""))
    if not message:
        message = _DEFAULT_REPLY
    if runtime_event_listener is not None:
        step = int(state.get("react_step", 0))
        runtime_event_listener(
            RuntimeEvent(
                run_id=str(state.get("conversation_key", "")),
                step=step,
                event_type="final_text",
                text=message,
            )
        )
        runtime_event_listener(
            RuntimeEvent(
                run_id=str(state.get("conversation_key", "")),
                step=step,
                event_type="run_completed",
                text=message,
            )
        )
    return {"reply_text": message}
