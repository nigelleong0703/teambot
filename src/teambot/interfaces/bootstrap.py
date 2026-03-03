from __future__ import annotations

from ..agents.core.service import AgentService


def build_agent_service() -> AgentService:
    """Single composition root for AgentService runtime wiring."""
    return AgentService()

