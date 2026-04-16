from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..runtime_paths import (
    get_active_skills_dir as _get_active_skills_dir,
    get_agent_skills_dir as _get_agent_skills_dir,
    get_agent_home,
    get_global_skills_dir as _get_global_skills_dir,
)
from .registry import RegisteredSkill, skill_registry


@dataclass(frozen=True)
class SkillDoc:
    name: str
    description: str
    when_to_use: str
    source: str
    path: str
    content: str


def get_working_dir() -> Path:
    return get_agent_home()


def get_builtin_skills_dir() -> Path:
    return Path(__file__).parent / "packs"


def get_global_skills_dir() -> Path:
    return _get_global_skills_dir()


def get_agent_skills_dir() -> Path:
    return _get_agent_skills_dir()


def get_customized_skills_dir() -> Path:
    return get_agent_skills_dir()


def get_active_skills_dir() -> Path:
    return _get_active_skills_dir()


def list_available_skills() -> list[str]:
    return [doc.name for doc in SkillService.list_available_skill_docs()]


def ensure_skills_initialized() -> None:
    SkillService._discover_all()


def _to_skill_doc(skill: RegisteredSkill) -> SkillDoc:
    return SkillDoc(
        name=skill.manifest.name,
        description=skill.manifest.description,
        when_to_use=skill.manifest.when_to_use,
        source="plugin",
        path="",
        content=skill.content,
    )


class SkillService:
    @staticmethod
    def _discover_all() -> None:
        skill_registry.discover(get_builtin_skills_dir())
        skill_registry.discover(get_global_skills_dir())
        skill_registry.discover(get_agent_skills_dir())

    @staticmethod
    def list_all_skills() -> list[SkillDoc]:
        SkillService._discover_all()
        return [_to_skill_doc(s) for s in skill_registry.list_all()]

    @staticmethod
    def list_available_skill_docs() -> list[SkillDoc]:
        SkillService._discover_all()
        return [_to_skill_doc(s) for s in skill_registry.list_all()]

    @staticmethod
    def get_skill_doc(name: str) -> SkillDoc | None:
        wanted = name.strip()
        for doc in SkillService.list_available_skill_docs():
            if doc.name == wanted:
                return doc
        return None

    @staticmethod
    def enable_skill(name: str, force: bool = False) -> bool:
        """Skills are enabled by placing a plugin package in a discovery directory."""
        SkillService._discover_all()
        return skill_registry.get(name) is not None

    @staticmethod
    def disable_skill(name: str) -> bool:
        """Unregister a skill from the in-memory registry."""
        return skill_registry.unregister(name)

    @staticmethod
    def sync_all(force: bool = False) -> tuple[int, int]:
        return 0, 0
