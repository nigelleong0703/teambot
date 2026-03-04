from __future__ import annotations

import os

from ...adapters.providers import ROLE_AGENT
from ...agent_core.contracts import ModelRoleInvoker
from ...models import AgentState
from ..prompts import build_general_reply_payload, general_reply_system_prompt
from .registry import ToolManifest, ToolRegistry


def _deterministic_general_reply(state: AgentState) -> dict[str, str]:
    text = state.get("user_text", "").strip()
    return {
        "message": (
            "Acknowledged. The MVP currently replies using deterministic thread routing."
            f"\n\nYou said: {text}"
        ),
    }


class _GeneralReplyTool:
    def __init__(self, provider_manager: ModelRoleInvoker | None) -> None:
        self._provider_manager = provider_manager

    def __call__(self, state: AgentState) -> dict[str, str]:
        manager = self._provider_manager
        if manager is None or not manager.has_role(ROLE_AGENT):
            return _deterministic_general_reply(state)

        try:
            result = manager.invoke_role_json(
                role=ROLE_AGENT,
                system_prompt=general_reply_system_prompt(),
                payload=build_general_reply_payload(state),
            )
        except Exception:
            return _deterministic_general_reply(state)

        message = result.data.get("message")
        if isinstance(message, str) and message.strip():
            return {"message": message.strip()}
        return _deterministic_general_reply(state)


def _echo_tool(state: AgentState) -> dict[str, str]:
    return {"message": f"tool_echo:{state.get('user_text', '')}"}


def _exec_tool_placeholder(_state: AgentState) -> dict[str, str]:
    return {
        "message": "exec_command blocked by policy or unauthorized.",
        "blocked": True,
    }


def build_tool_registry(
    provider_manager: ModelRoleInvoker | None = None,
) -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        ToolManifest(
            name="general_reply",
            description="Default conversational message tool.",
            risk_level="low",
        ),
        _GeneralReplyTool(provider_manager),
    )

    if os.getenv("ENABLE_ECHO_TOOL", "").strip().lower() in {"1", "true", "yes"}:
        registry.register(
            ToolManifest(
                name="tool_echo",
                description="Echo tool output for debugging action routing.",
                risk_level="low",
            ),
            _echo_tool,
        )

    if os.getenv("ENABLE_EXEC_TOOL", "").strip().lower() in {"1", "true", "yes"}:
        registry.register(
            ToolManifest(
                name="exec_command",
                description="High-risk command execution tool (placeholder).",
                risk_level="high",
            ),
            _exec_tool_placeholder,
        )

    return registry
