from __future__ import annotations

from dotenv import find_dotenv, load_dotenv

from ..agent.service import AgentService


def _load_local_env() -> None:
    dotenv_path = find_dotenv(usecwd=True)
    if dotenv_path:
        load_dotenv(dotenv_path=dotenv_path, override=False)


def build_agent_service(
    *,
    tools_config_path: str | None = None,
    tools_profile: str | None = None,
    strict_tools_config: bool = False,
) -> AgentService:
    """Single composition root for AgentService runtime wiring."""
    _load_local_env()
    return AgentService(
        tools_config_path=tools_config_path,
        tools_profile=tools_profile,
        strict_tools_config=strict_tools_config,
    )

