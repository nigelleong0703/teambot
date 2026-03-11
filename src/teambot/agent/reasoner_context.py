from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..domain.models import AgentState
from ..skills.context import build_reasoner_skill_context


@dataclass(frozen=True)
class ReasonerRequestContext:
    system_prompt_suffix: str
    payload_fields: dict[str, Any]


def _safe_str(value: object) -> str:
    if isinstance(value, str):
        return value.strip()
    return ""


def build_reasoner_request_context(state: AgentState) -> ReasonerRequestContext:
    payload_fields: dict[str, Any] = {}
    prompt_sections: list[str] = []

    recent_turns = state.get("recent_turns", [])
    if recent_turns:
        payload_fields["recent_turns"] = recent_turns

    conversation_summary = _safe_str(state.get("conversation_summary"))
    if conversation_summary:
        payload_fields["conversation_summary"] = conversation_summary

    runtime_working_dir = _safe_str(state.get("runtime_working_dir"))
    if runtime_working_dir:
        payload_fields["runtime_working_dir"] = runtime_working_dir

    skill_context = build_reasoner_skill_context(state)
    if skill_context.system_prompt_suffix:
        prompt_sections.append(skill_context.system_prompt_suffix)
    payload_fields.update(skill_context.payload_fields)

    memory_suffix = _safe_str(state.get("memory_system_prompt_suffix"))
    if memory_suffix:
        prompt_sections.append(memory_suffix)

    return ReasonerRequestContext(
        system_prompt_suffix="\n\n".join(prompt_sections),
        payload_fields=payload_fields,
    )
