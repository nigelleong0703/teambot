from __future__ import annotations

from dataclasses import dataclass

from .manager import SkillDoc, SkillService

_DEFAULT_MAX_SKILLS = 8
_DEFAULT_MAX_CONTENT_CHARS = 1200


@dataclass(frozen=True)
class ReasonerSkillContext:
    system_prompt_suffix: str
    payload_docs: list[dict[str, str]]


def _truncate(text: str, limit: int) -> str:
    if limit <= 0:
        return ""
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "\n...<truncated>"


def _to_payload_doc(doc: SkillDoc, *, max_content_chars: int) -> dict[str, str]:
    return {
        "name": doc.name,
        "description": doc.description,
        "source": doc.source,
        "path": doc.path,
        "content_excerpt": _truncate(doc.content, max_content_chars),
    }


def build_reasoner_skill_context(
    *,
    max_skills: int = _DEFAULT_MAX_SKILLS,
    max_content_chars: int = _DEFAULT_MAX_CONTENT_CHARS,
) -> ReasonerSkillContext:
    docs = SkillService.list_available_skill_docs()
    if max_skills > 0:
        docs = docs[:max_skills]

    if not docs:
        return ReasonerSkillContext(system_prompt_suffix="", payload_docs=[])

    rows: list[str] = []
    payload_docs: list[dict[str, str]] = []
    for doc in docs:
        description = doc.description.strip() or "No description"
        rows.append(f"- {doc.name}: {description}")
        payload_docs.append(_to_payload_doc(doc, max_content_chars=max_content_chars))

    system_prompt_suffix = "Active skill context:\n" + "\n".join(rows)
    return ReasonerSkillContext(
        system_prompt_suffix=system_prompt_suffix,
        payload_docs=payload_docs,
    )

