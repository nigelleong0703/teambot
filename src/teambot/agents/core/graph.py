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
        loop_guard = max(int(current.get("react_max_steps", 3)) + 2, 3)

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

        current["react_done"] = True
        current["reasoning_note"] = "Runtime guard triggered: loop limit exceeded, force finish."
        if not current.get("skill_output"):
            current["skill_output"] = {"message": "Processed."}
        current.update(compose_reply_node(current))
        return current


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
