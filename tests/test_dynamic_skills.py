from pathlib import Path

from teambot.skills import build_registry
from teambot.domain.models import AgentState


def _state(text: str = "hi") -> AgentState:
    return {
        "conversation_key": "T1:C1:1",
        "recent_turns": [],
        "conversation_summary": "",
        "memory_system_prompt_suffix": "",
        "event_type": "message",
        "user_text": text,
        "reaction": None,
        "react_step": 0,
        "react_max_steps": 3,
        "react_done": False,
        "react_notes": [],
        "reasoning_note": "",
        "selected_skill": "",
        "skill_input": {},
        "skill_output": {},
        "reply_text": "",
    }


def test_dynamic_skill_plugin_is_loaded_and_invokable(tmp_path: Path) -> None:
    plugin = tmp_path / "echo_skill.py"
    plugin.write_text(
        "\n".join(
            [
                "manifest = {",
                "    'name': 'echo_dynamic',",
                "    'description': 'Echo dynamic skill',",
                "}",
                "",
                "def handle(state):",
                "    return {'message': f\"echo:{state['user_text']}\"}",
                "",
            ]
        ),
        encoding="utf-8",
    )

    registry = build_registry(dynamic_skills_dir=str(tmp_path))
    output = registry.invoke("echo_dynamic", _state("hello dynamic"))

    assert output["message"] == "echo:hello dynamic"

