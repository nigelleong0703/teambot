from __future__ import annotations

from ...models import AgentState
from ...agent_core.contracts import ActionPluginRegistry
from ..skills.registry import SkillRegistry
from ..tools.registry import ToolRegistry
from .actions import ActionRegistry
from .executor import (
    build_act_node,
    compose_reply_node,
    observe_node,
    route_after_observe,
)
from .policy import ExecutionPolicyGate
from .router import build_reason_node, route_after_reason

_RUNTIME_GUARD_PADDING = 2
_RUNTIME_GUARD_MIN = 3
_FALLBACK_MESSAGE = "Processed."


def _loop_guard(state: AgentState) -> int:
    max_steps = int(state.get("react_max_steps", 3))
    return max(max_steps + _RUNTIME_GUARD_PADDING, _RUNTIME_GUARD_MIN)


def _finalize_guard_exit(state: AgentState) -> AgentState:
    state["react_done"] = True
    state["reasoning_note"] = "Runtime guard triggered: loop limit exceeded, force finish."
    if not state.get("skill_output"):
        state["skill_output"] = {"message": _FALLBACK_MESSAGE}
    state.update(compose_reply_node(state))
    return state


class AgentCoreRuntime:
    def __init__(
        self,
        *,
        action_registry: ActionRegistry,
        policy_gate: ExecutionPolicyGate,
    ) -> None:
        self.reason_node = build_reason_node(action_registry)
        self.act_node = build_act_node(action_registry, policy_gate)

    def invoke(self, state: AgentState) -> AgentState:
        current: AgentState = dict(state)
        loop_guard = _loop_guard(current)

        for _ in range(loop_guard):
            current.update(self.reason_node(current))
            next_step = route_after_reason(current)
            if next_step == "compose_reply":
                current.update(compose_reply_node(current))
                return current

            current.update(self.act_node(current))
            current.update(observe_node(current))
            next_step = route_after_observe(current)
            if next_step == "compose_reply":
                current.update(compose_reply_node(current))
                return current

        return _finalize_guard_exit(current)


def build_graph(
    registry: SkillRegistry,
    *,
    tool_registry: ToolRegistry | None = None,
    plugin_registry: ActionPluginRegistry | None = None,
    policy_gate: ExecutionPolicyGate | None = None,
):
    if policy_gate is None:
        policy_gate = ExecutionPolicyGate.from_env()

    action_registry = ActionRegistry(
        plugin_registry=plugin_registry,
        skill_registry=registry,
        tool_registry=tool_registry,
    )
    return AgentCoreRuntime(
        action_registry=action_registry,
        policy_gate=policy_gate,
    )
