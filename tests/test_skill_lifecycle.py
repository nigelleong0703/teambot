from teambot.skills.manager import (
    SkillService,
    ensure_skills_initialized,
    get_active_skills_dir,
    get_agent_skills_dir,
    list_available_skills,
)


def test_ensure_skills_initialized_does_not_mutate_active_dir() -> None:
    ensure_skills_initialized()
    assert "create_task" in set(list_available_skills())
    assert not get_active_skills_dir().exists()


def test_active_skill_docs_remain_catalog_only() -> None:
    active_dir = get_active_skills_dir()
    active_dir.mkdir(parents=True, exist_ok=True)

    create_task_dir = active_dir / "create_task"
    create_task_dir.mkdir(parents=True, exist_ok=True)
    (create_task_dir / "SKILL.md").write_text("name: create_task", encoding="utf-8")

    doc = SkillService.get_skill_doc("create_task")
    assert doc is not None
    assert doc.name == "create_task"


def test_enable_disable_skill_works_on_active_set() -> None:
    agent_skills_dir = get_agent_skills_dir()
    create_task_dir = agent_skills_dir / "create_task"
    create_task_dir.mkdir(parents=True, exist_ok=True)
    (create_task_dir / "SKILL.md").write_text("name: create_task", encoding="utf-8")

    assert SkillService.enable_skill("create_task", force=True) is True
    assert "create_task" in set(list_available_skills())

    assert SkillService.disable_skill("create_task") is True
    assert "create_task" in set(list_available_skills())
