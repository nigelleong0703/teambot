from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from teambot.contracts.contracts import ModelTextInvocationResult, ModelToolCall, ModelToolInvocationResult
from teambot.agent.graph import build_graph
from teambot.skills.manager import SkillDoc
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
        "recent_turns": [],
        "conversation_summary": "",
        "memory_system_prompt_suffix": "",
        "event_type": "message",
        "user_text": user_text,
        "reaction": None,
        "runtime_working_dir": "/tmp/teambot-work",
        "react_step": 0,
        "react_max_steps": 3,
        "react_done": False,
        "react_notes": [],
        "reasoning_note": "",
        "selected_action": "",
        "selected_skill": "",
        "action_input": {},
        "skill_input": {},
        "action_output": {},
        "skill_output": {},
        "active_skill_names": [],
        "active_skill_docs": [],
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
                    when_to_use="Before building new behavior.",
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
    graph = build_graph(tool_registry=tools, reasoner=reasoner)

    result = graph.invoke(_state("check my current time"))

    assert result["reply_text"] == "reasoner-final"
    assert reasoner.last_payload is not None
    assert "skill_catalog" in reasoner.last_payload
    assert isinstance(reasoner.last_payload["skill_catalog"], list)
    assert reasoner.last_payload["skill_catalog"][0]["name"] == "brainstorming"
    assert "Available skills" in reasoner.last_system_prompt


def test_reasoner_tool_schema_excludes_skills_and_event_handlers() -> None:
    from teambot.actions.event_handlers.builtin import build_registry as build_event_handler_registry
    from teambot.actions.registry import PluginHost
    from teambot.actions.tools import build_tool_registry

    tools = build_tool_registry(provider_manager=None)
    plugin_host = PluginHost()
    plugin_host.bind_event_handler_registry(build_event_handler_registry())
    plugin_host.bind_tool_registry(tools)

    reasoner = _ReasonerProbe()
    graph = build_graph(
        tool_registry=tools,
        plugin_registry=plugin_host,
        reasoner=reasoner,
    )

    result = graph.invoke(_state("what can you do?"))

    assert result["reply_text"] == "reasoner-final"
    assert reasoner.last_tools is not None
    tool_names = {tool.name for tool in reasoner.last_tools}
    assert "activate_skill" in tool_names
    assert "create_task" not in tool_names
    assert "handle_reaction" not in tool_names


def test_reasoner_request_includes_bounded_recent_conversation_turns() -> None:
    tools = ToolRegistry()
    tools.register(
        ToolManifest(name="get_current_time", description="time tool"),
        lambda _state: {"message": "time:ok"},
    )
    reasoner = _ReasonerProbe()
    graph = build_graph(tool_registry=tools, reasoner=reasoner)

    state = _state("what changed?")
    state["recent_turns"] = [
        {"role": "user", "text": "first question"},
        {"role": "assistant", "text": "first answer"},
        {"role": "user", "text": "x" * 500},
    ]

    result = graph.invoke(state)

    assert result["reply_text"] == "reasoner-final"
    assert reasoner.last_payload is not None
    assert reasoner.last_payload["recent_turns"][0] == {
        "role": "user",
        "text": "first question",
    }
    assert len(reasoner.last_payload["recent_turns"]) == 3
    assert reasoner.last_payload["recent_turns"][-1]["text"] == "x" * 500


def test_reasoner_request_includes_conversation_summary_and_long_term_memory_suffix() -> None:
    tools = ToolRegistry()
    tools.register(
        ToolManifest(name="get_current_time", description="time tool"),
        lambda _state: {"message": "time:ok"},
    )
    reasoner = _ReasonerProbe()
    graph = build_graph(tool_registry=tools, reasoner=reasoner)

    state = _state("what should we keep?")
    state["conversation_summary"] = "Earlier turns agreed to keep the SQLite-backed transcript store."
    state["memory_system_prompt_suffix"] = "Long-term memory:\n- Always keep diffs small."

    result = graph.invoke(state)

    assert result["reply_text"] == "reasoner-final"
    assert reasoner.last_payload is not None
    assert reasoner.last_payload["conversation_summary"] == state["conversation_summary"]
    assert "Long-term memory" in reasoner.last_system_prompt


def test_reasoner_request_includes_runtime_working_dir_context() -> None:
    tools = ToolRegistry()
    tools.register(
        ToolManifest(name="get_current_time", description="time tool"),
        lambda _state: {"message": "time:ok"},
    )
    reasoner = _ReasonerProbe()
    graph = build_graph(tool_registry=tools, reasoner=reasoner)

    state = _state("read the project files")
    state["runtime_working_dir"] = "/tmp/runtime-context"

    result = graph.invoke(state)

    assert result["reply_text"] == "reasoner-final"
    assert reasoner.last_payload is not None
    assert reasoner.last_payload["runtime_working_dir"] == "/tmp/runtime-context"


@dataclass
class _SkillActivationReasoner:
    calls: int = 0
    observed_payloads: list[dict[str, Any]] = field(default_factory=list)

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
        self.calls += 1
        self.observed_payloads.append(payload)
        if self.calls == 1:
            return ModelToolInvocationResult(
                text="",
                tool_calls=[ModelToolCall(name="activate_skill", arguments={"skill_name": "brainstorming"})],
                provider="stub",
                model="stub",
            )
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
        raise AssertionError("unexpected text-only path")


def test_activate_skill_loads_skill_doc_into_next_reasoner_request(monkeypatch) -> None:
    from teambot.skills import manager as skill_manager
    from teambot.actions.tools import build_tool_registry

    monkeypatch.setattr(
        skill_manager.SkillService,
        "list_available_skill_docs",
        staticmethod(
            lambda: [
                SkillDoc(
                    name="brainstorming",
                    description="Explore requirements before implementation",
                    when_to_use="Before building new behavior.",
                    source="agent",
                    path="/tmp/brainstorming",
                    content="---\nname: brainstorming\ndescription: Explore requirements before implementation\nwhen_to_use: Before building new behavior.\n---\n# Brainstorming\nAsk clarifying questions and compare options.",
                )
            ]
        ),
    )

    reasoner = _SkillActivationReasoner()
    graph = build_graph(
        tool_registry=build_tool_registry(provider_manager=None),
        reasoner=reasoner,
    )

    result = graph.invoke(_state("help me design this feature"))

    assert result["reply_text"] == "reasoner-final"
    assert len(reasoner.observed_payloads) == 2
    second_payload = reasoner.observed_payloads[1]
    assert second_payload["active_skill_docs"][0]["name"] == "brainstorming"
    assert "Brainstorming" in second_payload["active_skill_docs"][0]["content"]
