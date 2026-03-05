"""Agent orchestration package."""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .core.service import AgentService as AgentService
    from .react_agent import TeamBotReactAgent as TeamBotReactAgent

__all__ = ["AgentService", "TeamBotReactAgent"]


def __getattr__(name: str) -> Any:
    if name == "AgentService":
        from .core.service import AgentService as _AgentService

        return _AgentService
    if name == "TeamBotReactAgent":
        from .react_agent import TeamBotReactAgent as _TeamBotReactAgent

        return _TeamBotReactAgent
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
