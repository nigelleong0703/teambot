"""Agent runtime package."""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .graph import build_graph as build_graph
    from .runtime import TeamBotRuntime as TeamBotRuntime
    from .service import AgentService as AgentService

__all__ = ["build_graph", "AgentService", "TeamBotRuntime"]


def __getattr__(name: str) -> Any:
    if name == "build_graph":
        from .graph import build_graph as _build_graph

        return _build_graph
    if name == "AgentService":
        from .service import AgentService as _AgentService

        return _AgentService
    if name == "TeamBotRuntime":
        from .runtime import TeamBotRuntime as _TeamBotRuntime

        return _TeamBotRuntime
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
