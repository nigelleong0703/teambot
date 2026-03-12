from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from ..runtime_paths import (
    get_active_skills_dir as _get_active_skills_dir,
    get_agent_skills_dir as _get_agent_skills_dir,
    get_agent_home,
    get_global_skills_dir as _get_global_skills_dir,
)

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


def _collect_skills_from_dir(directory: Path) -> dict[str, Path]:
    skills: dict[str, Path] = {}
    if not directory.exists():
        return skills
    for skill_dir in directory.iterdir():
        if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
            skills[skill_dir.name] = skill_dir
    return skills


def _skill_source_dirs(*, include_legacy_active: bool) -> list[tuple[str, Path]]:
    sources: list[tuple[str, Path]] = [
        ("builtin", get_builtin_skills_dir()),
        ("global", get_global_skills_dir()),
        ("agent", get_agent_skills_dir()),
    ]
    if include_legacy_active:
        sources.append(("active", get_active_skills_dir()))
    return sources


def _collect_loaded_skills(*, include_legacy_active: bool) -> dict[str, Path]:
    merged: dict[str, Path] = {}
    for _, directory in _skill_source_dirs(include_legacy_active=include_legacy_active):
        merged.update(_collect_skills_from_dir(directory))
    return merged


def sync_skills_to_active(
    skill_names: list[str] | None = None,
    force: bool = False,
) -> tuple[int, int]:
    skills_to_sync = _collect_loaded_skills(include_legacy_active=False)
    if skill_names is not None:
        wanted = set(skill_names)
        skills_to_sync = {
            name: path for name, path in skills_to_sync.items() if name in wanted
        }

    active_dir = get_active_skills_dir()
    active_dir.mkdir(parents=True, exist_ok=True)

    synced = 0
    skipped = 0
    for name, source_dir in skills_to_sync.items():
        target_dir = active_dir / name
        if target_dir.exists() and not force:
            skipped += 1
            continue
        if target_dir.exists():
            shutil.rmtree(target_dir)
        shutil.copytree(source_dir, target_dir)
        synced += 1
    return synced, skipped


def list_available_skills() -> list[str]:
    return [doc.name for doc in SkillService.list_available_skill_docs()]


def ensure_skills_initialized() -> None:
    return


def _parse_frontmatter(content: str) -> tuple[str, str, str]:
    name = ""
    description = ""
    when_to_use = ""
    if not content.startswith("---"):
        return name, description, when_to_use
    parts = content.split("---", 2)
    if len(parts) < 3:
        return name, description, when_to_use
    fm = parts[1]
    for line in fm.splitlines():
        line = line.strip()
        if line.startswith("name:"):
            name = line.split(":", 1)[1].strip().strip("'\"")
        elif line.startswith("description:"):
            description = line.split(":", 1)[1].strip().strip("'\"")
        elif line.startswith("when_to_use:"):
            when_to_use = line.split(":", 1)[1].strip().strip("'\"")
    return name, description, when_to_use


def _read_skills_from_dir(directory: Path, source: str) -> list[SkillDoc]:
    docs: list[SkillDoc] = []
    if not directory.exists():
        return docs
    for skill_dir in sorted(directory.iterdir()):
        if not skill_dir.is_dir():
            continue
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue
        content = skill_md.read_text(encoding="utf-8")
        name, description, when_to_use = _parse_frontmatter(content)
        docs.append(
            SkillDoc(
                name=name or skill_dir.name,
                description=description,
                when_to_use=when_to_use,
                source=source,
                path=str(skill_dir),
                content=content,
            )
        )
    return docs


def _merge_skill_docs(*, include_legacy_active: bool) -> list[SkillDoc]:
    merged: dict[str, SkillDoc] = {}
    for source, directory in _skill_source_dirs(include_legacy_active=include_legacy_active):
        for doc in _read_skills_from_dir(directory, source):
            merged[doc.name] = doc
    return [merged[name] for name in sorted(merged)]


class SkillService:
    @staticmethod
    def list_all_skills() -> list[SkillDoc]:
        return _merge_skill_docs(include_legacy_active=True)

    @staticmethod
    def list_available_skill_docs() -> list[SkillDoc]:
        return _merge_skill_docs(include_legacy_active=True)

    @staticmethod
    def get_skill_doc(name: str) -> SkillDoc | None:
        wanted = name.strip()
        if not wanted:
            return None
        for doc in SkillService.list_available_skill_docs():
            if doc.name == wanted:
                return doc
        return None

    @staticmethod
    def enable_skill(name: str, force: bool = False) -> bool:
        sync_skills_to_active(skill_names=[name], force=force)
        return name in set(list_available_skills())

    @staticmethod
    def disable_skill(name: str) -> bool:
        target = get_active_skills_dir() / name
        if not target.exists():
            return False
        shutil.rmtree(target)
        return True

    @staticmethod
    def sync_all(force: bool = False) -> tuple[int, int]:
        return sync_skills_to_active(skill_names=None, force=force)
