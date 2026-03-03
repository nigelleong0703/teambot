from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from teambot.agents.planner import ReasoningModelPlanner
from teambot.agents.providers.base import NormalizedResponse, ProviderEndpoint, ProviderRoleBinding, ProviderSettings
from teambot.agents.providers.registry import ProviderClientRegistry
from teambot.agents.providers.router import ROLE_AGENT, ROLE_ROUTER, ProviderManager
from teambot.agents.skills.registry import SkillManifest
from teambot.models import AgentState


@dataclass
class _PlannerClient:
    endpoint: ProviderEndpoint
    response_text: str

    def invoke(
        self,
        *,
        system_prompt: str,
        payload: dict,
        on_token: Callable[[str], None] | None = None,
    ) -> NormalizedResponse:
        if on_token is not None:
            on_token(self.response_text)
        return NormalizedResponse(
            text=self.response_text,
            finish_reason="stop",
            usage={"total_tokens": 1},
            raw={"system_prompt": system_prompt, "payload": payload},
        )


def _state(text: str = "hello") -> AgentState:
    return {
        "conversation_key": "T1:C1:1",
        "event_type": "message",
        "user_text": text,
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


def _skills() -> list[SkillManifest]:
    return [
        SkillManifest(name="general_reply", description=""),
        SkillManifest(name="create_task", description=""),
        SkillManifest(name="handle_reaction", description=""),
    ]


def test_planner_uses_router_role_when_router_can_decide() -> None:
    router_endpoint = ProviderEndpoint(provider="openai-compatible", model="router")
    settings = ProviderSettings(
        role_bindings={
            ROLE_AGENT: ProviderRoleBinding(role=ROLE_AGENT, endpoints=[ProviderEndpoint(provider="openai-compatible", model="agent")]),
            ROLE_ROUTER: ProviderRoleBinding(role=ROLE_ROUTER, endpoints=[router_endpoint]),
        }
    )

    manager = ProviderManager(
        settings=settings,
        client_registry=ProviderClientRegistry(
            client_factory=lambda endpoint: _PlannerClient(
                endpoint=endpoint,
                response_text='{"use_agent_model": false, "selected_skill": "create_task", "note": "cheap route"}',
            )
        ),
    )
    planner = ReasoningModelPlanner(provider_manager=manager)
    result = planner.plan(_state("/todo x"), _skills())

    assert result.selected_skill == "create_task"
    assert "Router model" in result.note


def test_planner_falls_through_to_agent_role_when_router_escalates() -> None:
    router_endpoint = ProviderEndpoint(provider="openai-compatible", model="router")
    agent_endpoint = ProviderEndpoint(provider="openai-compatible", model="agent")
    settings = ProviderSettings(
        role_bindings={
            ROLE_AGENT: ProviderRoleBinding(role=ROLE_AGENT, endpoints=[agent_endpoint]),
            ROLE_ROUTER: ProviderRoleBinding(role=ROLE_ROUTER, endpoints=[router_endpoint]),
        }
    )

    def _factory(endpoint: ProviderEndpoint):
        if endpoint.model == "router":
            return _PlannerClient(
                endpoint=endpoint,
                response_text='{"use_agent_model": true, "selected_skill": "", "note": "escalate"}',
            )
        return _PlannerClient(
            endpoint=endpoint,
            response_text='{"done": false, "selected_skill": "create_task", "skill_input": {}, "final_message": "", "note": "agent decision"}',
        )

    manager = ProviderManager(
        settings=settings,
        client_registry=ProviderClientRegistry(client_factory=_factory),
    )
    planner = ReasoningModelPlanner(provider_manager=manager)
    result = planner.plan(_state("/todo x"), _skills())

    assert result.selected_skill == "create_task"
    assert result.note == "agent decision"
