from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..domain.models import AgentState
from .manager import SkillDoc, SkillService

_DEFAULT_MAX_SKILLS = 8
_DEFAULT_MAX_CONTENT_CHARS = 1200


@dataclass(frozen=True)
class ReasonerSkillContext:
    system_prompt_suffix: str
    payload_fields: dict[str, Any]


def _truncate(text: str, limit: int) -> str:
    if limit <= 0:
        return ""
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "\n...<truncated>"


def _catalog_payload_doc(doc: SkillDoc) -> dict[str, str]:
    return {
        "name": doc.name,
        "description": doc.description,
        "when_to_use": doc.when_to_use,
        "source": doc.source,
        "path": doc.path,
    }


def _active_skill_doc(doc: dict[str, Any], *, max_content_chars: int) -> dict[str, str]:
    return {
        "name": str(doc.get("name") or ""),
        "description": str(doc.get("description") or ""),
        "source": str(doc.get("source") or ""),
        "path": str(doc.get("path") or ""),
        "content": _truncate(str(doc.get("content") or ""), max_content_chars),
    }


def _active_skill_docs_from_state(state: AgentState, *, max_content_chars: int) -> list[dict[str, str]]:
    raw_docs = state.get("active_skill_docs", [])
    if not isinstance(raw_docs, list):
        return []
    docs: list[dict[str, str]] = []
    for raw in raw_docs:
        if not isinstance(raw, dict):
            continue
        docs.append(_active_skill_doc(raw, max_content_chars=max_content_chars))
    return docs


def build_reasoner_skill_context(
    state: AgentState,
    *,
    max_skills: int = _DEFAULT_MAX_SKILLS,
    max_content_chars: int = _DEFAULT_MAX_CONTENT_CHARS,
) -> ReasonerSkillContext:
    docs = SkillService.list_available_skill_docs()
    if max_skills > 0:
        docs = docs[:max_skills]

    rows: list[str] = []
    payload_fields: dict[str, Any] = {}
    if docs:
        payload_fields["skill_catalog"] = [_catalog_payload_doc(doc) for doc in docs]
        rows.append("Available skills:")
        for doc in docs:
            description = doc.description.strip() or "No description"
            when_to_use = doc.when_to_use.strip()
            if when_to_use:
                rows.append(f"- {doc.name}: {description} (Use when: {when_to_use})")
            else:
                rows.append(f"- {doc.name}: {description}")

    active_docs = _active_skill_docs_from_state(state, max_content_chars=max_content_chars)
    if active_docs:
        payload_fields["active_skill_docs"] = active_docs
        rows.append("Active skill instructions loaded:")
        for doc in active_docs:
            rows.append(f"- {doc['name']}")

    return ReasonerSkillContext(
        system_prompt_suffix="\n".join(rows).strip(),
        payload_fields=payload_fields,
    )
