from __future__ import annotations

from ...contracts.contracts import ModelRoleInvoker
from .config import load_runtime_tool_config
from .runtime_builder import build_runtime_tool_registry
from .registry import ToolRegistry


def build_tool_registry(
    provider_manager: ModelRoleInvoker | None = None,
) -> ToolRegistry:
    config = load_runtime_tool_config()
    return build_runtime_tool_registry(
        profile=config.profile,
        provider_manager=provider_manager,
        namesake_strategy=config.namesake_strategy,
        enable_echo_tool=config.enable_echo_tool,
        enable_exec_alias=config.enable_exec_alias,
        enable_tools=config.enable_tools,
        disable_tools=config.disable_tools,
    )
