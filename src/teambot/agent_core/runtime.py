"""Compatibility runtime import surface for the new agent_core package."""

from ..agents.core.graph import AgentCoreRuntime, build_graph

__all__ = ["AgentCoreRuntime", "build_graph"]
