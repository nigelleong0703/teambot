from __future__ import annotations

from ..agents.core.service import AgentService


def build_agent_service(
    *,
    tools_config_path: str | None = None,
    tools_profile: str | None = None,
    strict_tools_config: bool = False,
) -> AgentService:
    """Single composition root for AgentService runtime wiring."""
    return AgentService(
        tools_config_path=tools_config_path,
        tools_profile=tools_profile,
        strict_tools_config=strict_tools_config,
    )

