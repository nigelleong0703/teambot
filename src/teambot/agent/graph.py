from __future__ import annotations

from typing import Callable

from ..actions.registry import PluginHost
from ..actions.event_handlers.builtin import build_registry as build_event_handler_registry
from ..actions.tools.registry import ToolRegistry
from ..contracts.contracts import ActionPluginRegistry
from ..contracts.contracts import ModelRoleInvoker
from ..domain.models import AgentState, RuntimeEvent
from .execution import (
    action_output_update,
    build_act_node,
    compose_reply_node,
    get_action_output,
    observe_node,
)
from .policy import ExecutionPolicyGate
from .reason import build_reason_node

_RUNTIME_GUARD_PADDING = 2
_RUNTIME_GUARD_MIN = 3
_FALLBACK_MESSAGE = "Processed."


def _loop_guard(state: AgentState) -> int:
    max_steps = int(state.get("react_max_steps", 3))
    return max(max_steps + _RUNTIME_GUARD_PADDING, _RUNTIME_GUARD_MIN)


def _finalize_guard_exit(
    state: AgentState,
    runtime_event_listener: Callable[[RuntimeEvent], None] | None = None,
) -> AgentState:
    state["react_done"] = True
    state["reasoning_note"] = "Runtime guard triggered: loop limit exceeded, force finish."
    if not get_action_output(state):
        state.update(action_output_update({"message": _FALLBACK_MESSAGE}))
    state.update(compose_reply_node(state, runtime_event_listener=runtime_event_listener))
    return state


def _compose_and_return(
    state: AgentState,
    runtime_event_listener: Callable[[RuntimeEvent], None] | None = None,
) -> AgentState:
    state.update(compose_reply_node(state, runtime_event_listener=runtime_event_listener))
    return state


class AgentCoreRuntime:
    def __init__(
        self,
        *,
        action_registry: ActionPluginRegistry,
        policy_gate: ExecutionPolicyGate,
        reasoner: ModelRoleInvoker | None = None,
        planner: ModelRoleInvoker | None = None,
        runtime_event_listener: Callable[[RuntimeEvent], None] | None = None,
    ) -> None:
        selected_reasoner = reasoner or planner
        self.runtime_event_listener = runtime_event_listener
        self.reason_node = build_reason_node(
            action_registry,
            reasoner=selected_reasoner,
            runtime_event_listener=runtime_event_listener,
        )
        self.act_node = build_act_node(action_registry, policy_gate)

    def invoke(self, state: AgentState) -> AgentState:
        current: AgentState = dict(state)
        loop_guard = _loop_guard(current)

        for _ in range(loop_guard):
            current.update(self.reason_node(current))
            if current.get("react_done", False):
                return _compose_and_return(
                    current,
                    runtime_event_listener=self.runtime_event_listener,
                )

            if self.runtime_event_listener is not None:
                selected_action = str(
                    current.get("selected_action") or current.get("selected_skill") or ""
                ).strip()
                if selected_action:
                    selected_input = current.get("action_input")
                    if not isinstance(selected_input, dict):
                        selected_input = {}
                    self.runtime_event_listener(
                        RuntimeEvent(
                            run_id=str(current.get("conversation_key", "")),
                            step=int(current.get("react_step", 0)) + 1,
                            event_type="tool_call",
                            action_name=selected_action,
                            action_input=selected_input,
                        )
                    )

            current.update(self.act_node(current))
            current.update(
                observe_node(
                    current,
                    runtime_event_listener=self.runtime_event_listener,
                )
            )
            if current.get("react_done", True):
                return _compose_and_return(
                    current,
                    runtime_event_listener=self.runtime_event_listener,
                )

        return _finalize_guard_exit(
            current,
            runtime_event_listener=self.runtime_event_listener,
        )


def build_graph(
    *,
    tool_registry: ToolRegistry | None = None,
    plugin_registry: ActionPluginRegistry | None = None,
    policy_gate: ExecutionPolicyGate | None = None,
    reasoner: ModelRoleInvoker | None = None,
    planner: ModelRoleInvoker | None = None,
    runtime_event_listener: Callable[[RuntimeEvent], None] | None = None,
):
    if policy_gate is None:
        policy_gate = ExecutionPolicyGate.from_env()

    action_registry = plugin_registry
    if action_registry is None:
        host = PluginHost()
        host.bind_event_handler_registry(build_event_handler_registry())
        host.bind_tool_registry(tool_registry)
        action_registry = host
    return AgentCoreRuntime(
        action_registry=action_registry,
        policy_gate=policy_gate,
        reasoner=reasoner or planner,
        runtime_event_listener=runtime_event_listener,
    )
