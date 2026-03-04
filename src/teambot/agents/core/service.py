from __future__ import annotations

import os
from typing import Any, Callable

from ...adapters.tools import ToolRegistry, build_tool_registry
from ...adapters.providers import ROLE_AGENT, ProviderManager, build_default_provider_manager
from ...models import InboundEvent, OutboundReply, ReplyTarget
from ...plugins.registry import PluginHost
from ...store import MemoryStore
from ..skills import SkillRegistry, build_registry
from ..skills.manager import (
    ensure_skills_initialized,
    list_available_skills,
)
from .graph import build_graph
from .policy import ExecutionPolicyGate
from .state import build_initial_state


class AgentService:
    def __init__(self) -> None:
        self.store = MemoryStore()
        self.dynamic_skills_dir = os.getenv("SKILLS_DIR", "").strip() or None
        self.provider_manager: ProviderManager | None = build_default_provider_manager()
        self.registry: SkillRegistry
        self.tool_registry: ToolRegistry
        self.plugin_host: PluginHost
        self.policy_gate = ExecutionPolicyGate.from_env()
        self.graph = None
        self.reload_runtime()

    def set_model_event_listener(
        self,
        listener: Callable[[str, dict[str, Any]], None] | None,
    ) -> None:
        if self.provider_manager is None:
            return
        if not self.provider_manager.has_role(ROLE_AGENT):
            return
        self.provider_manager.set_event_listener(listener)

    def reload_runtime(self) -> None:
        ensure_skills_initialized()
        active_names = set(list_available_skills())
        enabled = active_names if active_names else None
        self.registry = build_registry(
            dynamic_skills_dir=self.dynamic_skills_dir,
            enabled_skill_names=enabled,
        )
        self.tool_registry = build_tool_registry(provider_manager=self.provider_manager)
        self.plugin_host = PluginHost()
        self.plugin_host.bind_skill_registry(self.registry)
        self.plugin_host.bind_tool_registry(self.tool_registry)
        self.graph = build_graph(
            self.registry,
            tool_registry=self.tool_registry,
            plugin_registry=self.plugin_host,
            policy_gate=self.policy_gate,
        )

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
        result = self.graph.invoke(state)
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
