"""Agent orchestration package."""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .core.service import AgentService as AgentService

__all__ = ["AgentService"]


def __getattr__(name: str) -> Any:
    if name == "AgentService":
        from .core.service import AgentService as _AgentService

        return _AgentService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
