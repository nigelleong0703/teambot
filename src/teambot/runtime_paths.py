from __future__ import annotations

import os
from pathlib import Path

_DEFAULT_AGENT_HOME = Path("~/.teambot/agents/default")


def get_agent_home(agent_home: str | Path | None = None) -> Path:
    raw = agent_home
    if raw is None:
        raw = os.getenv("AGENT_HOME", "").strip() or os.getenv("WORKING_DIR", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return _DEFAULT_AGENT_HOME.expanduser().resolve()


def get_agent_system_dir(agent_home: str | Path | None = None) -> Path:
    return get_agent_home(agent_home) / "system"


def get_agent_work_dir(agent_home: str | Path | None = None) -> Path:
    return get_agent_home(agent_home) / "work"


def get_platform_root(agent_home: str | Path | None = None) -> Path:
    home = get_agent_home(agent_home)
    if home.parent.name == "agents":
        return home.parent.parent
    return home.parent


def get_global_skills_dir(agent_home: str | Path | None = None) -> Path:
    return get_platform_root(agent_home) / "skills"


def get_agent_skills_dir(agent_home: str | Path | None = None) -> Path:
    raw = os.getenv("CUSTOMIZED_SKILLS_DIR", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()

    home = get_agent_home(agent_home)
    preferred = home / "skills"
    legacy = get_agent_system_dir(agent_home) / "customized_skills"
    if preferred.exists() or not legacy.exists():
        return preferred
    return legacy


def get_customized_skills_dir(agent_home: str | Path | None = None) -> Path:
    return get_agent_skills_dir(agent_home)


def get_active_skills_dir(agent_home: str | Path | None = None) -> Path:
    raw = os.getenv("ACTIVE_SKILLS_DIR", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return get_agent_system_dir(agent_home) / "active_skills"


def get_dynamic_skills_dir(agent_home: str | Path | None = None) -> Path:
    raw = os.getenv("SKILLS_DIR", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return get_agent_system_dir(agent_home) / "skills"


def resolve_dynamic_skills_dir(agent_home: str | Path | None = None) -> str | None:
    path = get_dynamic_skills_dir(agent_home)
    if path.exists():
        return str(path)
    return None


def ensure_agent_home_layout(agent_home: str | Path | None = None) -> Path:
    home = get_agent_home(agent_home)
    (home / "system").mkdir(parents=True, exist_ok=True)
    (home / "work").mkdir(parents=True, exist_ok=True)
    (home / "skills").mkdir(parents=True, exist_ok=True)
    return home
