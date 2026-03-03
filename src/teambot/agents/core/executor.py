from __future__ import annotations

from ...models import AgentState
from .actions import ActionRegistry
from .policy import ExecutionPolicyGate


def build_act_node(action_registry: ActionRegistry, policy_gate: ExecutionPolicyGate):
    def _act(state: AgentState) -> dict:
        action_name = state["selected_skill"]
        action = action_registry.get_action(action_name)
        decision = policy_gate.check(action.name, action.risk_level)
        if not decision.allowed:
            output = {
                "message": decision.reason or f"Action blocked: {action_name}",
                "blocked": True,
            }
        else:
            output = action_registry.invoke(action_name, state)
        return {"skill_output": output}

    return _act


def observe_node(state: AgentState) -> dict:
    step = state.get("react_step", 0) + 1
    max_steps = state.get("react_max_steps", 3)
    follow_up_skill = state.get("skill_output", {}).get("next_skill")
    done = (not follow_up_skill) or (step >= max_steps)

    notes = list(state.get("react_notes", []))
    trace = list(state.get("execution_trace", []))
    message = state.get("skill_output", {}).get("message", "")
    selected_skill = state.get("selected_skill", "")
    blocked = bool(state.get("skill_output", {}).get("blocked", False))
    notes.append(
        f"step={step} skill={selected_skill} "
        f"observation={message}"
    )
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


def route_after_observe(state: AgentState) -> str:
    return "compose_reply" if state.get("react_done", True) else "reason"


def compose_reply_node(state: AgentState) -> dict:
    message = state.get("skill_output", {}).get("message", "")
    if not message:
        message = "Processed."
    return {"reply_text": message}
