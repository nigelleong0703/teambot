from __future__ import annotations

import os
from typing import Any, Callable

from ..providers.manager import ProviderManager
from ..tools.registry import ToolRegistry
from ...domain.models import InboundEvent, OutboundReply, ReplyTarget
from ...plugins.registry import PluginHost
from ...domain.store import MemoryStore
from ..react_agent import TeamBotReactAgent
from ..mcp.manager import MCPClientManager
from ..skills import SkillRegistry
from .state import build_initial_state


class AgentService:
    def __init__(self) -> None:
        self.store = MemoryStore()
        self.dynamic_skills_dir = os.getenv("SKILLS_DIR", "").strip() or None
        self.provider_manager: ProviderManager | None
        self.registry: SkillRegistry
        self.tool_registry: ToolRegistry
        self.plugin_host: PluginHost
        self.mcp_manager: MCPClientManager
        self.mcp_aliases: dict[str, str] = {}
        self.policy_gate = None
        self.graph = None
        self._agent = TeamBotReactAgent(
            dynamic_skills_dir=self.dynamic_skills_dir,
        )
        self.reload_runtime()

    def set_model_event_listener(
        self,
        listener: Callable[[str, dict[str, Any]], None] | None,
    ) -> None:
        self._agent.set_model_event_listener(listener)

    def _sync_runtime_handles(self) -> None:
        self.provider_manager = self._agent.provider_manager
        self.registry = self._agent.registry
        self.tool_registry = self._agent.tool_registry
        self.plugin_host = self._agent.plugin_host
        self.mcp_manager = self._agent.mcp_manager
        self.mcp_aliases = self._agent.mcp_aliases
        self.policy_gate = self._agent.policy_gate
        self.graph = self._agent.graph

    def reload_runtime(self) -> None:
        self._agent.reload_runtime()
        self._sync_runtime_handles()

    async def process_event(self, event: InboundEvent) -> OutboundReply:
        existing = await self.store.get_processed_event(event.event_id)
        if existing is not None:
            return existing

        target = ReplyTarget(
            team_id=event.team_id,
            channel_id=event.channel_id,
            thread_ts=event.thread_ts,
        )
        conversation = await self.store.upsert_conversation(target)

        state = build_initial_state(
            event=event,
            conversation_key=conversation.conversation_key,
        )
        result = self._agent.invoke(state)
        reply = OutboundReply(
            event_id=event.event_id,
            conversation_key=conversation.conversation_key,
            reply_target=conversation.reply_target,
            text=result["reply_text"],
            skill_name=result["selected_skill"],
        )

        user_text = event.text or f"reaction:{event.reaction}"
        await self.store.append_turns(
            conversation_key=conversation.conversation_key,
            user_text=user_text,
            assistant_text=reply.text,
        )
        await self.store.save_processed_event(event.event_id, reply)
        return reply

