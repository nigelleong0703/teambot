from __future__ import annotations

import logging
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SkillDoc:
    name: str
    description: str
    source: str
    path: str
    content: str


def get_working_dir() -> Path:
    return Path(os.getenv("WORKING_DIR", "~/.teambot")).expanduser().resolve()


def get_builtin_skills_dir() -> Path:
    return Path(__file__).parent / "packs"


def get_customized_skills_dir() -> Path:
    raw = os.getenv("CUSTOMIZED_SKILLS_DIR", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return get_working_dir() / "customized_skills"


def get_active_skills_dir() -> Path:
    raw = os.getenv("ACTIVE_SKILLS_DIR", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return get_working_dir() / "active_skills"


def _collect_skills_from_dir(directory: Path) -> dict[str, Path]:
    skills: dict[str, Path] = {}
    if not directory.exists():
        return skills
    for skill_dir in directory.iterdir():
        if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
            skills[skill_dir.name] = skill_dir
    return skills


def sync_skills_to_active(
    skill_names: list[str] | None = None,
    force: bool = False,
) -> tuple[int, int]:
    builtin = _collect_skills_from_dir(get_builtin_skills_dir())
    customized = _collect_skills_from_dir(get_customized_skills_dir())

    # Customized overrides builtin with same name.
    skills_to_sync = {**builtin, **customized}
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
    active_dir = get_active_skills_dir()
    if not active_dir.exists():
        return []
    return sorted(
        d.name
        for d in active_dir.iterdir()
        if d.is_dir() and (d / "SKILL.md").exists()
    )


def ensure_skills_initialized() -> None:
    active_dir = get_active_skills_dir()
    active = list_available_skills()
    if active:
        return
    logger.warning(
        "No active skills found in %s. Runtime will load no skills until sync/enable is performed.",
        active_dir,
    )


def _parse_frontmatter(content: str) -> tuple[str, str]:
    name = ""
    description = ""
    if not content.startswith("---"):
        return name, description
    parts = content.split("---", 2)
    if len(parts) < 3:
        return name, description
    fm = parts[1]
    for line in fm.splitlines():
        line = line.strip()
        if line.startswith("name:"):
            name = line.split(":", 1)[1].strip().strip("'\"")
        elif line.startswith("description:"):
            description = line.split(":", 1)[1].strip().strip("'\"")
    return name, description


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
        name, description = _parse_frontmatter(content)
        docs.append(
            SkillDoc(
                name=name or skill_dir.name,
                description=description,
                source=source,
                path=str(skill_dir),
                content=content,
            )
        )
    return docs


class SkillService:
    @staticmethod
    def list_all_skills() -> list[SkillDoc]:
        return [
            *_read_skills_from_dir(get_builtin_skills_dir(), "builtin"),
            *_read_skills_from_dir(get_customized_skills_dir(), "customized"),
        ]

    @staticmethod
    def list_available_skill_docs() -> list[SkillDoc]:
        return _read_skills_from_dir(get_active_skills_dir(), "active")

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
