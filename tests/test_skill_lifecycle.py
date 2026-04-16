from teambot.skills.manager import (
    SkillService,
    ensure_skills_initialized,
    get_active_skills_dir,
    get_agent_skills_dir,
    list_available_skills,
)
from teambot.skills.registry import SkillManifest, skill_registry


def test_ensure_skills_initialized_discovers_builtin_handle_reaction() -> None:
    ensure_skills_initialized()
    assert "handle_reaction" in set(list_available_skills())
    assert not get_active_skills_dir().exists()


def test_skill_registered_directly_is_available() -> None:
    skill_registry.register(
        SkillManifest(name="test_direct_skill", description="direct registration test"),
        content="# Direct\nRegistered directly in test.",
    )
    try:
        assert "test_direct_skill" in set(list_available_skills())
        doc = SkillService.get_skill_doc("test_direct_skill")
        assert doc is not None
        assert doc.content == "# Direct\nRegistered directly in test."
        assert doc.description == "direct registration test"
    finally:
        skill_registry.unregister("test_direct_skill")


def test_skill_plugin_discovered_from_directory(tmp_path) -> None:
    skill_dir = tmp_path / "my_plugin_skill"
    skill_dir.mkdir()
    (skill_dir / "__init__.py").write_text(
        "from teambot.skills.registry import skill_registry, SkillManifest\n"
        "skill_registry.register(\n"
        "    SkillManifest(name='my_plugin_skill', description='plugin test'),\n"
        "    content='plugin content',\n"
        ")\n",
        encoding="utf-8",
    )

    skill_registry.discover(tmp_path)

    doc = SkillService.get_skill_doc("my_plugin_skill")
    assert doc is not None
    assert doc.content == "plugin content"
    skill_registry.unregister("my_plugin_skill")


def test_disable_skill_unregisters_from_memory() -> None:
    skill_registry.register(
        SkillManifest(name="temp_skill", description="temp"),
        content="temp",
    )
    assert SkillService.get_skill_doc("temp_skill") is not None
    assert SkillService.disable_skill("temp_skill") is True
    assert SkillService.get_skill_doc("temp_skill") is None


def test_enable_skill_returns_true_when_skill_exists() -> None:
    skill_registry.register(
        SkillManifest(name="enabled_skill", description="enabled"),
        content="enabled content",
    )
    try:
        assert SkillService.enable_skill("enabled_skill") is True
    finally:
        skill_registry.unregister("enabled_skill")
