from __future__ import annotations

import os

from ...models import AgentState
from .registry import ToolManifest, ToolRegistry


def _echo_tool(state: AgentState) -> dict[str, str]:
    return {"message": f"tool_echo:{state.get('user_text', '')}"}


def _exec_tool_placeholder(_state: AgentState) -> dict[str, str]:
    return {
        "message": "exec_command blocked by policy or unauthorized.",
        "blocked": True,
    }


def build_tool_registry() -> ToolRegistry:
    registry = ToolRegistry()

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
