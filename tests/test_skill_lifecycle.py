from teambot.skills.manager import (
    SkillService,
    ensure_skills_initialized,
    get_active_skills_dir,
    get_agent_skills_dir,
    list_available_skills,
)


def test_ensure_skills_initialized_does_not_mutate_active_dir() -> None:
    ensure_skills_initialized()
    assert "handle_reaction" in set(list_available_skills())
    assert not get_active_skills_dir().exists()


def test_active_skill_docs_remain_catalog_only() -> None:
    active_dir = get_active_skills_dir()
    active_dir.mkdir(parents=True, exist_ok=True)

    custom_skill_dir = active_dir / "custom_skill"
    custom_skill_dir.mkdir(parents=True, exist_ok=True)
    (custom_skill_dir / "SKILL.md").write_text("name: custom_skill", encoding="utf-8")

    doc = SkillService.get_skill_doc("custom_skill")
    assert doc is not None
    assert doc.name == "custom_skill"


def test_enable_disable_skill_works_on_active_set() -> None:
    agent_skills_dir = get_agent_skills_dir()
    custom_skill_dir = agent_skills_dir / "custom_skill"
    custom_skill_dir.mkdir(parents=True, exist_ok=True)
    (custom_skill_dir / "SKILL.md").write_text("name: custom_skill", encoding="utf-8")

    assert SkillService.enable_skill("custom_skill", force=True) is True
    assert "custom_skill" in set(list_available_skills())

    assert SkillService.disable_skill("custom_skill") is True
    assert "custom_skill" in set(list_available_skills())
