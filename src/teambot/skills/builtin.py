from __future__ import annotations

from .dynamic import load_dynamic_skills
from .registry import SkillRegistry


def build_registry(
    dynamic_skills_dir: str | None = None,
    enabled_skill_names: set[str] | None = None,
) -> SkillRegistry:
    _ = enabled_skill_names
    registry = SkillRegistry()
    if dynamic_skills_dir:
        # Built-in deterministic handlers are modeled as event handlers.
        # Skills are reserved for dynamic/optional plugin capabilities.
        load_dynamic_skills(registry, dynamic_skills_dir)
    return registry

