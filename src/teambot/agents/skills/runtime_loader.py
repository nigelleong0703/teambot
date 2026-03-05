from __future__ import annotations

from .builtin import build_registry
from .manager import ensure_skills_initialized, list_available_skills
from .registry import SkillRegistry


def build_runtime_skill_registry(
    *,
    dynamic_skills_dir: str | None = None,
) -> SkillRegistry:
    ensure_skills_initialized()
    active_names = set(list_available_skills())
    return build_registry(
        dynamic_skills_dir=dynamic_skills_dir,
        enabled_skill_names=active_names,
    )
