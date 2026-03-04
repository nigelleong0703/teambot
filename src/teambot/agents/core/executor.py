from __future__ import annotations

from ...models import AgentState
from .actions import ActionRegistry
from .policy import ExecutionPolicyGate

_DEFAULT_REPLY = "Processed."


def _blocked_action_output(action_name: str, reason: str) -> dict[str, object]:
    return {
        "message": reason or f"Action blocked: {action_name}",
        "blocked": True,
    }


def _is_observation_done(step: int, max_steps: int, follow_up_skill: object) -> bool:
    return (not follow_up_skill) or (step >= max_steps)


def build_act_node(action_registry: ActionRegistry, policy_gate: ExecutionPolicyGate):
    def _act(state: AgentState) -> dict:
        action_name = state["selected_skill"]
        action = action_registry.get_action(action_name)
        decision = policy_gate.check(action.name, action.risk_level)
        if not decision.allowed:
            output = _blocked_action_output(action_name, decision.reason or "")
        else:
            output = action_registry.invoke(action_name, state)
        return {"skill_output": output}

    return _act


def observe_node(state: AgentState) -> dict:
    step = int(state.get("react_step", 0)) + 1
    max_steps = int(state.get("react_max_steps", 3))
    follow_up_skill = state.get("skill_output", {}).get("next_skill")
    done = _is_observation_done(step, max_steps, follow_up_skill)

    notes = list(state.get("react_notes", []))
    trace = list(state.get("execution_trace", []))
    message = str(state.get("skill_output", {}).get("message", ""))
    selected_skill = state.get("selected_skill", "")
    blocked = bool(state.get("skill_output", {}).get("blocked", False))
    notes.append(f"step={step} skill={selected_skill} observation={message}")
    trace.append(
        {
            "step": step,
            "action": selected_skill,
            "blocked": blocked,
            "observation": message,
        }
    )
    return {
        "react_step": step,
        "react_done": done,
        "react_notes": notes,
        "execution_trace": trace,
    }


def compose_reply_node(state: AgentState) -> dict:
    message = str(state.get("skill_output", {}).get("message", ""))
    if not message:
        message = _DEFAULT_REPLY
    return {"reply_text": message}
