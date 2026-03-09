from __future__ import annotations

from pathlib import Path

from ...runtime_paths import get_agent_system_dir

DEFAULT_SYSTEM_PROMPT = "You are TeamBot, a helpful assistant."


def _resolve_prompt_root(working_dir: str | Path | None) -> Path:
    if working_dir is not None:
        return Path(working_dir).expanduser().resolve()
    return get_agent_system_dir()


def _strip_frontmatter(content: str) -> str:
    text = content.strip()
    if not text.startswith("---"):
        return text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return text
    return parts[2].strip()


def _read_prompt_file(path: Path) -> str:
    if not path.exists():
        return ""
    return _strip_frontmatter(path.read_text(encoding="utf-8"))


def build_system_prompt_from_working_dir(
    working_dir: str | Path | None = None,
) -> str:
    resolved = _resolve_prompt_root(working_dir)

    sections: list[str] = []
    required_agents = _read_prompt_file(resolved / "AGENTS.md")
    if not required_agents:
        return DEFAULT_SYSTEM_PROMPT

    sections.append("# AGENTS.md")
    sections.append("")
    sections.append(required_agents)

    for optional_name in ("SOUL.md", "PROFILE.md"):
        optional_content = _read_prompt_file(resolved / optional_name)
        if not optional_content:
            continue
        sections.append("")
        sections.append(f"# {optional_name}")
        sections.append("")
        sections.append(optional_content)

    return "\n".join(sections).strip() or DEFAULT_SYSTEM_PROMPT
