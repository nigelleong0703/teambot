from pathlib import Path
from teambot.skills.registry import skill_registry, SkillManifest

skill_registry.register(
    SkillManifest(
        name="handle_reaction",
        description="Map Slack reactions to deterministic task state updates.",
    ),
    content=(Path(__file__).parent / "SKILL.md").read_text(encoding="utf-8"),
)
