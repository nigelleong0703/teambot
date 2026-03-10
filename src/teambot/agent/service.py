from __future__ import annotations

import asyncio
from typing import Any, Callable

from ..domain.models import AgentState, InboundEvent, OutboundReply, ReplyTarget, RuntimeEvent
from ..domain.store import MemoryStore
from ..actions.registry import PluginHost
from ..actions.event_handlers.registry import EventHandlerRegistry
from ..actions.tools.registry import ToolRegistry
from ..mcp.manager import MCPClientManager
from ..providers.manager import ProviderManager
from ..skills import SkillRegistry
from ..memory import (
    CharBudgetMemoryPolicy,
    MemoryContextAssembler,
    ProviderBackedSummaryGenerator,
    SessionCompactionResult,
    SessionMemoryManager,
)
from ..runtime_paths import resolve_dynamic_skills_dir
from .runtime import TeamBotRuntime
from .state import build_initial_state


class AgentService:
    def __init__(
        self,
        *,
        tools_config_path: str | None = None,
        tools_profile: str | None = None,
        strict_tools_config: bool = False,
    ) -> None:
        self.store = MemoryStore()
        self.memory_policy = CharBudgetMemoryPolicy()
        self.dynamic_skills_dir = resolve_dynamic_skills_dir()
        self.provider_manager: ProviderManager | None
        self.registry: SkillRegistry
        self.event_handler_registry: EventHandlerRegistry
        self.tool_registry: ToolRegistry
        self.plugin_host: PluginHost
        self.mcp_manager: MCPClientManager
        self.mcp_aliases: dict[str, str] = {}
        self.policy_gate = None
        self.graph = None
        self._agent = TeamBotRuntime(
            dynamic_skills_dir=self.dynamic_skills_dir,
            tools_config_path=tools_config_path,
            tools_profile=tools_profile,
            strict_tools_config=strict_tools_config,
        )
        self._sync_runtime_handles()
        self.memory_context_assembler = MemoryContextAssembler()
        self.session_memory = self._build_session_memory_manager()

    def set_model_event_listener(
        self,
        listener: Callable[[str, dict[str, Any]], None] | None,
    ) -> None:
        self._agent.set_model_event_listener(listener)

    def _sync_runtime_handles(self) -> None:
        self.provider_manager = self._agent.provider_manager
        self.registry = self._agent.registry
        self.event_handler_registry = self._agent.event_handler_registry
        self.tool_registry = self._agent.tool_registry
        self.plugin_host = self._agent.plugin_host
        self.mcp_manager = self._agent.mcp_manager
        self.mcp_aliases = self._agent.mcp_aliases
        self.policy_gate = self._agent.policy_gate
        self.graph = self._agent.graph

    def _build_session_memory_manager(self) -> SessionMemoryManager:
        return SessionMemoryManager(
            store=self.store,
            policy=self.memory_policy,
            summary_generator=ProviderBackedSummaryGenerator(
                reasoner=self.provider_manager,
                max_summary_chars=self.memory_policy.summary_max_chars,
                max_turn_text_chars=self.memory_policy.summary_turn_max_chars,
            ),
        )

    def reload_runtime(self) -> None:
        self._agent.reload_runtime()
        self._sync_runtime_handles()
        self.session_memory = self._build_session_memory_manager()

    @staticmethod
    def _build_reply(
        *,
        event: InboundEvent,
        conversation_key: str,
        reply_target: ReplyTarget,
        result: dict[str, Any],
    ) -> OutboundReply:
        return OutboundReply(
            event_id=event.event_id,
            conversation_key=conversation_key,
            reply_target=reply_target,
            text=result["reply_text"],
            skill_name=str(result.get("selected_action") or result.get("selected_skill") or ""),
            reasoning_note=str(result.get("reasoning_note") or ""),
            execution_trace=list(result.get("execution_trace") or []),
        )

    async def _build_runtime_state(
        self,
        *,
        event: InboundEvent,
        reply_target: ReplyTarget,
    ) -> tuple[ReplyTarget, AgentState]:
        session_context = await self.session_memory.load_context(reply_target)
        memory_context = self.memory_context_assembler.build(
            session_context=session_context,
        )
        state = build_initial_state(
            event=event,
            conversation_key=session_context.conversation_key,
            memory_context=memory_context,
        )
        return session_context.reply_target, state

    @staticmethod
    def _compaction_runtime_event(
        *,
        conversation_key: str,
        current_step: int,
        result: SessionCompactionResult,
    ) -> RuntimeEvent | None:
        if not result.compacted:
            return None
        return RuntimeEvent(
            run_id=conversation_key,
            step=current_step,
            event_type="memory_compacted",
            text="Compacted summary",
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
        reply_target, state = await self._build_runtime_state(event=event, reply_target=target)
        result = self._agent.invoke(state)
        reply = self._build_reply(
            event=event,
            conversation_key=str(state["conversation_key"]),
            reply_target=reply_target,
            result=result,
        )

        user_text = event.text or f"reaction:{event.reaction}"
        await self.session_memory.append_turns(
            conversation_key=str(state["conversation_key"]),
            user_text=user_text,
            assistant_text=reply.text,
        )
        await self.store.save_processed_event(event.event_id, reply)
        return reply

    async def stream_event(self, event: InboundEvent):
        existing = await self.store.get_processed_event(event.event_id)
        if existing is not None:
            yield RuntimeEvent(
                run_id=existing.conversation_key,
                step=0,
                event_type="run_completed",
                text=existing.text,
            )
            return

        target = ReplyTarget(
            team_id=event.team_id,
            channel_id=event.channel_id,
            thread_ts=event.thread_ts,
        )
        reply_target, state = await self._build_runtime_state(event=event, reply_target=target)

        queue: asyncio.Queue[RuntimeEvent | object] = asyncio.Queue()
        sentinel = object()
        loop = asyncio.get_running_loop()
        current_step = {"value": 1}
        pending_completion = {"event": None}

        previous_listener = None
        if self.provider_manager is not None:
            previous_listener = getattr(self.provider_manager, "_event_listener", None)

        def _emit(runtime_event: RuntimeEvent) -> None:
            if runtime_event.step > 0:
                current_step["value"] = runtime_event.step
            if runtime_event.event_type == "run_completed":
                pending_completion["event"] = runtime_event
                return
            loop.call_soon_threadsafe(queue.put_nowait, runtime_event)

        def _provider_event_listener(name: str, payload: dict[str, Any]) -> None:
            if previous_listener is not None:
                previous_listener(name, payload)
            if name == "model_reasoning_token":
                token = str(payload.get("token", ""))
                if token:
                    loop.call_soon_threadsafe(
                        queue.put_nowait,
                        RuntimeEvent(
                            run_id=str(state["conversation_key"]),
                            step=current_step["value"],
                            event_type="thinking_delta",
                            text=token,
                        ),
                    )
            elif name == "model_token":
                token = str(payload.get("token", ""))
                if token:
                    loop.call_soon_threadsafe(
                        queue.put_nowait,
                        RuntimeEvent(
                            run_id=str(state["conversation_key"]),
                            step=current_step["value"],
                            event_type="final_delta",
                            text=token,
                        ),
                    )
        
        if self.provider_manager is not None:
            self.provider_manager.set_event_listener(_provider_event_listener)

        async def _run_and_store() -> OutboundReply:
            try:
                result = await asyncio.to_thread(
                    self._agent.invoke,
                    state,
                    _emit,
                )
                reply = self._build_reply(
                    event=event,
                    conversation_key=str(state["conversation_key"]),
                    reply_target=reply_target,
                    result=result,
                )
                user_text = event.text or f"reaction:{event.reaction}"
                compaction = await self.session_memory.append_turns(
                    conversation_key=str(state["conversation_key"]),
                    user_text=user_text,
                    assistant_text=reply.text,
                )
                compaction_event = self._compaction_runtime_event(
                    conversation_key=str(state["conversation_key"]),
                    current_step=current_step["value"],
                    result=compaction,
                )
                if compaction_event is not None:
                    _emit(compaction_event)
                completed_event = pending_completion["event"]
                if isinstance(completed_event, RuntimeEvent):
                    loop.call_soon_threadsafe(queue.put_nowait, completed_event)
                await self.store.save_processed_event(event.event_id, reply)
                return reply
            finally:
                if self.provider_manager is not None:
                    self.provider_manager.set_event_listener(previous_listener)
                loop.call_soon_threadsafe(queue.put_nowait, sentinel)

        runner = asyncio.create_task(_run_and_store())
        try:
            while True:
                item = await queue.get()
                if item is sentinel:
                    break
                assert isinstance(item, RuntimeEvent)
                yield item
        finally:
            await runner
