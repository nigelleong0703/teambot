from __future__ import annotations

import os

from ...agent_core.contracts import ModelRoleInvoker
from .external_operation_tools import env_enabled
from .runtime_builder import build_runtime_tool_registry
from .registry import ToolRegistry


def _env_enabled(name: str) -> bool:
    return env_enabled(name)


def build_tool_registry(
    provider_manager: ModelRoleInvoker | None = None,
) -> ToolRegistry:
    profile = os.getenv("TOOLS_PROFILE", "minimal")
    namesake_strategy = os.getenv("TOOLS_NAMESAKE_STRATEGY", "skip")
    return build_runtime_tool_registry(
        profile=profile,
        provider_manager=provider_manager,
        namesake_strategy=namesake_strategy,
        enable_echo_tool=_env_enabled("ENABLE_ECHO_TOOL"),
        enable_exec_alias=_env_enabled("ENABLE_EXEC_TOOL"),
    )
