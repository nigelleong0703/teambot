from pathlib import Path

from teambot.skills.manager import (
    SkillService,
    ensure_skills_initialized,
    get_active_skills_dir,
    list_available_skills,
)
from teambot.skills.runtime_loader import build_runtime_skill_registry


def test_ensure_skills_initialized_does_not_mutate_active_dir() -> None:
    ensure_skills_initialized()
    assert list_available_skills() == []
    assert not get_active_skills_dir().exists()


def test_runtime_registry_does_not_promote_active_skill_docs_to_actions() -> None:
    active_dir = get_active_skills_dir()
    active_dir.mkdir(parents=True, exist_ok=True)

    create_task_dir = active_dir / "create_task"
    create_task_dir.mkdir(parents=True, exist_ok=True)
    (create_task_dir / "SKILL.md").write_text("name: create_task", encoding="utf-8")

    registry = build_runtime_skill_registry(dynamic_skills_dir=None)
    names = {manifest.name for manifest in registry.list_manifests()}
    assert names == set()


def test_enable_disable_skill_works_on_active_set() -> None:
    assert SkillService.enable_skill("create_task", force=True) is True
    assert "create_task" in set(list_available_skills())

    assert SkillService.disable_skill("create_task") is True
    assert "create_task" not in set(list_available_skills())


def test_runtime_registry_can_load_dynamic_plugins(tmp_path: Path) -> None:
    plugin = tmp_path / "echo_skill.py"
    plugin.write_text(
        "\n".join(
            [
                "manifest = {'name': 'echo_dynamic', 'description': 'Echo dynamic skill'}",
                "def handle(state):",
                "    return {'message': f\"echo:{state['user_text']}\"}",
            ]
        ),
        encoding="utf-8",
    )
    registry = build_runtime_skill_registry(dynamic_skills_dir=str(tmp_path))
    names = {manifest.name for manifest in registry.list_manifests()}
    assert "echo_dynamic" in names

