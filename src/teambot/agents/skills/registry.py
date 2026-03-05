from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from ...domain.models import AgentState

SkillHandler = Callable[[AgentState], dict[str, Any]]


@dataclass(frozen=True)
class SkillManifest:
    name: str
    description: str
    timeout_seconds: int = 20


@dataclass(frozen=True)
class Skill:
    manifest: SkillManifest
    handler: SkillHandler


class SkillRegistry:
    def __init__(self) -> None:
        self._skills: dict[str, Skill] = {}

    def register(self, manifest: SkillManifest, handler: SkillHandler) -> None:
        if manifest.name in self._skills:
            raise ValueError(f"skill already registered: {manifest.name}")
        self._skills[manifest.name] = Skill(manifest=manifest, handler=handler)

    def require(self, name: str) -> Skill:
        skill = self._skills.get(name)
        if skill is None:
            raise KeyError(f"skill not found: {name}")
        return skill

    def invoke(self, name: str, state: AgentState) -> dict[str, Any]:
        return self.require(name).handler(state)

    def list_manifests(self) -> list[SkillManifest]:
        return [skill.manifest for skill in self._skills.values()]

