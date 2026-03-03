from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Protocol

from ..agent_core.contracts import ModelRoleInvoker
from ..models import AgentState
from ..adapters.providers import (
    ROLE_AGENT,
    ROLE_ROUTER,
    ProviderInvocationError,
    ProviderManager,
    build_default_provider_manager,
)
from .skills.registry import SkillManifest


class PlannerError(RuntimeError):
    pass


@dataclass(frozen=True)
class PlanResult:
    selected_skill: str = ""
    skill_input: dict[str, Any] = field(default_factory=dict)
    done: bool = False
    final_message: str = ""
    note: str = ""


class Planner(Protocol):
    def plan(
        self,
        state: AgentState,
        available_skills: list[SkillManifest],
    ) -> PlanResult:
        ...


class RulePlanner:
    """Deterministic fallback planner for local/dev use."""

    def plan(
        self,
        state: AgentState,
        available_skills: list[SkillManifest],
    ) -> PlanResult:
        skill_names = {s.name for s in available_skills}
        if state["event_type"] == "reaction_added" and "handle_reaction" in skill_names:
            return PlanResult(
                selected_skill="handle_reaction",
                note="Rule planner: reaction_added -> handle_reaction",
            )

        text = state["user_text"].strip().lower()
        if text.startswith("/todo") and "create_task" in skill_names:
            return PlanResult(
                selected_skill="create_task",
                note="Rule planner: /todo -> create_task",
            )

        default_skill = "general_reply" if "general_reply" in skill_names else ""
        return PlanResult(
            selected_skill=default_skill,
            note="Rule planner: default -> general_reply",
        )


class ReasoningModelPlanner:
    """Planner backed by provider manager role bindings."""

    def __init__(
        self,
        *,
        provider_manager: ModelRoleInvoker,
    ) -> None:
        self.provider_manager = provider_manager
        self._skill_documents: list[dict[str, str]] = []

    def set_skill_documents(self, docs: list[dict[str, str]]) -> None:
        self._skill_documents = docs

    @classmethod
    def from_env(cls) -> "ReasoningModelPlanner | None":
        manager = build_default_provider_manager()
        if manager is None:
            return None
        if not manager.has_role(ROLE_AGENT):
            return None
        return cls(provider_manager=manager)

    def plan(
        self,
        state: AgentState,
        available_skills: list[SkillManifest],
    ) -> PlanResult:
        skill_names = {skill.name for skill in available_skills}
        skill_specs = [
            {"name": skill.name, "description": skill.description}
            for skill in available_skills
        ]

        if self.provider_manager.has_role(ROLE_ROUTER):
            routed = self._try_router(
                state=state,
                allowed_skills=skill_names,
                skill_specs=skill_specs,
            )
            if routed is not None:
                return routed

        return self._plan_with_agent(
            state=state,
            allowed_skills=skill_names,
            skill_specs=skill_specs,
        )

    def _try_router(
        self,
        *,
        state: AgentState,
        allowed_skills: set[str],
        skill_specs: list[dict[str, str]],
    ) -> PlanResult | None:
        system_prompt = (
            "You are a low-cost router model. Return JSON only.\n"
            "Schema: {\n"
            '  "use_agent_model": boolean,\n'
            '  "selected_skill": string,\n'
            '  "note": string\n'
            "}\n"
            "Rules:\n"
            "- If task is ambiguous or requires deeper reasoning, set use_agent_model=true.\n"
            "- If use_agent_model=false, selected_skill must be in available_skills.\n"
        )
        payload = {
            "event_type": state.get("event_type"),
            "user_text": state.get("user_text"),
            "reaction": state.get("reaction"),
            "available_skills": skill_specs,
        }
        try:
            result = self.provider_manager.invoke_role_json(
                role=ROLE_ROUTER,
                system_prompt=system_prompt,
                payload=payload,
            )
            raw = result.data
        except ProviderInvocationError:
            return None

        use_agent_model = bool(raw.get("use_agent_model", True))
        selected_skill = str(raw.get("selected_skill", "")).strip()
        note = str(raw.get("note", "")).strip() or "router"

        if use_agent_model:
            return None
        if not selected_skill or selected_skill not in allowed_skills:
            return None
        return PlanResult(
            selected_skill=selected_skill,
            note=f"Router model: {note}",
        )

    def _plan_with_agent(
        self,
        *,
        state: AgentState,
        allowed_skills: set[str],
        skill_specs: list[dict[str, str]],
    ) -> PlanResult:
        system_prompt = (
            "You are a planning module in a ReAct workflow. "
            "Return a single JSON object only. No markdown.\n"
            "Schema: {\n"
            '  "selected_skill": string,\n'
            '  "skill_input": object,\n'
            '  "done": boolean,\n'
            '  "final_message": string,\n'
            '  "note": string\n'
            "}\n"
            "Rules:\n"
            "- If done is true, final_message should be non-empty.\n"
            "- If done is false, selected_skill must be one of available skills.\n"
            "- Keep note concise."
        )
        payload = {
            "event_type": state.get("event_type"),
            "user_text": state.get("user_text"),
            "reaction": state.get("reaction"),
            "react_step": state.get("react_step"),
            "react_max_steps": state.get("react_max_steps"),
            "previous_skill": state.get("selected_skill"),
            "last_observation": state.get("skill_output", {}),
            "available_skills": skill_specs,
            "active_skill_docs": self._skill_documents,
        }
        try:
            result = self.provider_manager.invoke_role_json(
                role=ROLE_AGENT,
                system_prompt=system_prompt,
                payload=payload,
            )
            raw = result.data
        except ProviderInvocationError as exc:
            raise PlannerError(self._format_provider_error(exc)) from exc
        except Exception as exc:
            raise PlannerError(f"agent role invocation failed: {exc}") from exc
        return self._parse_plan(raw, allowed_skills=allowed_skills)

    @staticmethod
    def _format_provider_error(exc: ProviderInvocationError) -> str:
        if not exc.attempts:
            return str(exc)
        details = "; ".join(
            f"{a.provider}/{a.model}@{a.endpoint or 'default'}: {a.error}"
            for a in exc.attempts
        )
        return f"{exc}. attempts={details}"

    def _parse_plan(
        self,
        raw: dict[str, Any],
        *,
        allowed_skills: set[str],
    ) -> PlanResult:
        if not isinstance(raw, dict):
            raise PlannerError("planner output must be object")

        done = bool(raw.get("done", False))
        selected_skill = str(raw.get("selected_skill", "")).strip()
        final_message = str(raw.get("final_message", "")).strip()
        note = str(raw.get("note", "")).strip()
        skill_input = raw.get("skill_input", {})
        if not isinstance(skill_input, dict):
            skill_input = {}

        if done:
            return PlanResult(
                done=True,
                final_message=final_message or "Processed.",
                note=note or "Model planner: finish directly",
            )
        if not selected_skill:
            raise PlannerError("planner output missing selected_skill")
        if selected_skill not in allowed_skills:
            raise PlannerError(f"planner selected unknown skill: {selected_skill}")
        return PlanResult(
            selected_skill=selected_skill,
            skill_input=skill_input,
            done=False,
            final_message="",
            note=note or f"Model planner: execute {selected_skill}",
        )


def parse_json_object(raw: str) -> dict[str, Any]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise PlannerError("invalid JSON object") from exc
    if not isinstance(data, dict):
        raise PlannerError("JSON must be object")
    return data
