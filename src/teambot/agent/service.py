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
from ..memory import (
    CharBudgetMemoryPolicy,
    MemoryContextAssembler,
    ProviderBackedSummaryGenerator,
    SessionCompactionResult,
    SessionMemoryManager,
)
from .prompts.system_prompt import build_system_prompt_from_working_dir
from .reason import _reasoner_prompt
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
        self.provider_manager: ProviderManager | None
        self.event_handler_registry: EventHandlerRegistry
        self.tool_registry: ToolRegistry
        self.plugin_host: PluginHost
        self.mcp_manager: MCPClientManager
        self.mcp_aliases: dict[str, str] = {}
        self.policy_gate = None
        self.graph = None
        self._agent = TeamBotRuntime(
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

    def _build_system_prompt(self, session_context: Any) -> str:
        from .prompts.system_prompt import DEFAULT_SYSTEM_PROMPT
        custom = build_system_prompt_from_working_dir()
        if custom and custom != DEFAULT_SYSTEM_PROMPT:
            base = f"{custom}\n\n{_reasoner_prompt()}"
        else:
            base = _reasoner_prompt()
        summary = getattr(session_context, "conversation_summary", "")
        if summary:
            base = f"{base}\n\n## Conversation summary\n{summary}"
        return base

    @staticmethod
    def _session_to_messages(session_context: Any) -> list[dict[str, Any]]:
        """Convert session recent_turns to a messages list for the loop."""
        messages = []
        for turn in getattr(session_context, "recent_turns", []):
            role = turn.get("role", "") if isinstance(turn, dict) else getattr(turn, "role", "")
            text = turn.get("text", "") if isinstance(turn, dict) else getattr(turn, "text", "")
            if role and text:
                messages.append({"role": role, "content": text})
        return messages

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

    async def process_event(
        self,
        event: InboundEvent,
        on_approval_required: Callable[[str, dict[str, Any]], bool] | None = None,
    ) -> OutboundReply:
        existing = await self.store.get_processed_event(event.event_id)
        if existing is not None:
            return existing

        target = ReplyTarget(
            team_id=event.team_id,
            channel_id=event.channel_id,
            thread_ts=event.thread_ts,
        )
        session_context = await self.session_memory.load_context(target)
        reply_target = session_context.reply_target
        conversation_key = session_context.conversation_key

        messages = self._session_to_messages(session_context)
        user_text = event.text or f"reaction:{event.reaction}"
        messages.append({"role": "user", "content": user_text})

        system_prompt = self._build_system_prompt(session_context)
        final_text, _, usage = self._agent.run_loop(
            messages=messages,
            system_prompt=system_prompt,
            conversation_key=conversation_key,
            on_approval_required=on_approval_required,
        )

        reply = OutboundReply(
            event_id=event.event_id,
            conversation_key=conversation_key,
            reply_target=reply_target,
            text=final_text,
            skill_name="",
            reasoning_note="",
        )

        await self.session_memory.append_turns(
            conversation_key=conversation_key,
            user_text=user_text,
            assistant_text=final_text,
            input_tokens=usage.get("input_tokens"),
            output_tokens=usage.get("output_tokens"),
        )
        await self.store.save_processed_event(event.event_id, reply)
        return reply

    async def stream_event(
        self,
        event: InboundEvent,
        on_approval_required: Callable[[str, dict[str, Any]], bool] | None = None,
    ):
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
        session_context = await self.session_memory.load_context(target)
        reply_target = session_context.reply_target
        conversation_key = session_context.conversation_key

        messages = self._session_to_messages(session_context)
        user_text = event.text or f"reaction:{event.reaction}"
        messages.append({"role": "user", "content": user_text})
        system_prompt = self._build_system_prompt(session_context)

        queue: asyncio.Queue[RuntimeEvent | object] = asyncio.Queue()
        sentinel = object()
        event_loop = asyncio.get_running_loop()

        def _on_event(runtime_event: RuntimeEvent) -> None:
            event_loop.call_soon_threadsafe(queue.put_nowait, runtime_event)

        def _on_token(token: str) -> None:
            event_loop.call_soon_threadsafe(
                queue.put_nowait,
                RuntimeEvent(
                    run_id=conversation_key,
                    step=0,
                    event_type="final_delta",
                    text=token,
                ),
            )

        async def _run_and_store() -> None:
            try:
                final_text, _, usage = await asyncio.to_thread(
                    self._agent.run_loop,
                    messages=messages,
                    system_prompt=system_prompt,
                    conversation_key=conversation_key,
                    on_token=_on_token,
                    on_event=_on_event,
                    on_approval_required=on_approval_required,
                )
                reply = OutboundReply(
                    event_id=event.event_id,
                    conversation_key=conversation_key,
                    reply_target=reply_target,
                    text=final_text,
                    skill_name="",
                    reasoning_note="",
                )
                compaction = await self.session_memory.append_turns(
                    conversation_key=conversation_key,
                    user_text=user_text,
                    assistant_text=final_text,
                    input_tokens=usage.get("input_tokens"),
                    output_tokens=usage.get("output_tokens"),
                )
                await self.store.save_processed_event(event.event_id, reply)
                if compaction.compacted:
                    queue.put_nowait(RuntimeEvent(
                        run_id=conversation_key,
                        step=0,
                        event_type="memory_compacted",
                        text="Compacted summary",
                    ))
                queue.put_nowait(RuntimeEvent(
                    run_id=conversation_key,
                    step=0,
                    event_type="run_completed",
                    text=final_text,
                ))
            finally:
                event_loop.call_soon_threadsafe(queue.put_nowait, sentinel)

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
