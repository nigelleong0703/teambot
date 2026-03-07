from __future__ import annotations

from .dynamic import load_dynamic_skills
from .manager import ensure_skills_initialized
from .registry import SkillRegistry


def build_runtime_skill_registry(
    *,
    dynamic_skills_dir: str | None = None,
) -> SkillRegistry:
    ensure_skills_initialized()
    registry = SkillRegistry()
    if dynamic_skills_dir:
        load_dynamic_skills(registry, dynamic_skills_dir)
    return registry
