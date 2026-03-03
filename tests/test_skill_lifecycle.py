from teambot.agents.skills.manager import (
    SkillService,
    ensure_skills_initialized,
    list_available_skills,
)


def test_builtin_skills_are_synced_to_active_on_init() -> None:
    ensure_skills_initialized()
    names = set(list_available_skills())
    assert {"general_reply", "create_task", "handle_reaction"} <= names


def test_enable_disable_skill_works_on_active_set() -> None:
    ensure_skills_initialized()

    assert SkillService.disable_skill("create_task") is True
    assert "create_task" not in set(list_available_skills())

    assert SkillService.enable_skill("create_task") is True
    assert "create_task" in set(list_available_skills())
