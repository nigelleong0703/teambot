from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from teambot.contracts.contracts import ModelTextInvocationResult, ModelToolInvocationResult
from teambot.agent.graph import build_graph
from teambot.skills.manager import SkillDoc
from teambot.skills.registry import SkillRegistry
from teambot.actions.tools.registry import ToolManifest, ToolRegistry
from teambot.domain.models import AgentState


@dataclass
class _ReasonerProbe:
    last_system_prompt: str = ""
    last_payload: dict[str, Any] | None = None
    last_tools: list[Any] | None = None

    def has_role(self, role: str) -> bool:
        return role == "agent_model"

    def invoke_role_tools(
        self,
        *,
        role: str,
        system_prompt: str,
        payload: dict[str, Any],
        tools: list[Any],
    ) -> ModelToolInvocationResult:
        self.last_system_prompt = system_prompt
        self.last_payload = payload
        self.last_tools = tools
        return ModelToolInvocationResult(
            text="reasoner-final",
            tool_calls=[],
            provider="stub",
            model="stub",
        )

    def invoke_role_text(
        self,
        *,
        role: str,
        system_prompt: str,
        user_message: str,
    ) -> ModelTextInvocationResult:
        self.last_system_prompt = system_prompt
        self.last_payload = {"raw_user_message": user_message}
        return ModelTextInvocationResult(
            text="reasoner-final",
            provider="stub",
            model="stub",
        )


def _state(user_text: str) -> AgentState:
    return {
        "conversation_key": "T1:C1:1",
        "event_type": "message",
        "user_text": user_text,
        "reaction": None,
        "react_step": 0,
        "react_max_steps": 3,
        "react_done": False,
        "react_notes": [],
        "reasoning_note": "",
        "selected_skill": "",
        "skill_input": {},
        "skill_output": {},
        "execution_trace": [],
        "reply_text": "",
    }


def test_reasoner_request_includes_loaded_skill_context(monkeypatch) -> None:
    from teambot.skills import manager as skill_manager

    monkeypatch.setattr(
        skill_manager.SkillService,
        "list_available_skill_docs",
        staticmethod(
            lambda: [
                SkillDoc(
                    name="brainstorming",
                    description="Explore requirements before implementation",
                    source="agent",
                    path="/tmp/brainstorming",
                    content="# Brainstorming\nUse before creative implementation work.",
                )
            ]
        ),
    )

    tools = ToolRegistry()
    tools.register(
        ToolManifest(name="get_current_time", description="time tool"),
        lambda _state: {"message": "time:ok"},
    )
    reasoner = _ReasonerProbe()
    graph = build_graph(SkillRegistry(), tool_registry=tools, reasoner=reasoner)

    result = graph.invoke(_state("check my current time"))

    assert result["reply_text"] == "reasoner-final"
    assert reasoner.last_payload is not None
    assert "skill_docs" in reasoner.last_payload
    assert isinstance(reasoner.last_payload["skill_docs"], list)
    assert reasoner.last_payload["skill_docs"][0]["name"] == "brainstorming"
    assert "Loaded skill context" in reasoner.last_system_prompt


def test_reasoner_tool_schema_excludes_skills_and_event_handlers() -> None:
    from teambot.actions.event_handlers.builtin import build_registry as build_event_handler_registry
    from teambot.actions.registry import PluginHost
    from teambot.skills.registry import SkillManifest

    tools = ToolRegistry()
    tools.register(
        ToolManifest(name="get_current_time", description="time tool"),
        lambda _state: {"message": "time:ok"},
    )
    plugin_host = PluginHost()
    plugin_host.bind_event_handler_registry(build_event_handler_registry())
    skill_registry = SkillRegistry()
    skill_registry.register(
        SkillManifest(name="brainstorming", description="skill action"),
        lambda _state: {"message": "skill"},
    )
    plugin_host.bind_skill_registry(skill_registry)
    plugin_host.bind_tool_registry(tools)

    reasoner = _ReasonerProbe()
    graph = build_graph(
        skill_registry,
        tool_registry=tools,
        plugin_registry=plugin_host,
        reasoner=reasoner,
    )

    result = graph.invoke(_state("what can you do?"))

    assert result["reply_text"] == "reasoner-final"
    assert reasoner.last_tools is not None
    tool_names = {tool.name for tool in reasoner.last_tools}
    assert "get_current_time" in tool_names
    assert "brainstorming" not in tool_names
    assert "create_task" not in tool_names
    assert "handle_reaction" not in tool_names
