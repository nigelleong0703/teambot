from __future__ import annotations

from pathlib import Path

import pytest

from teambot.providers.registry import ROLE_AGENT
from teambot.agent.state import build_initial_state
from teambot.app.bootstrap import build_agent_service
from teambot.domain.models import InboundEvent


ROOT = Path(__file__).resolve().parents[1]


def test_api_cli_and_tui_use_bootstrap_composition_root() -> None:
    main_py = (ROOT / "src" / "teambot" / "app" / "main.py").read_text(encoding="utf-8")
    cli_py = (ROOT / "src" / "teambot" / "app" / "cli.py").read_text(encoding="utf-8")
    tui_py = (ROOT / "src" / "teambot" / "app" / "tui.py").read_text(encoding="utf-8")

    assert "from .bootstrap import build_agent_service" in main_py
    assert "from .bootstrap import build_agent_service" in cli_py
    assert "from .bootstrap import build_agent_service" in tui_py
    assert "service = build_agent_service()" in main_py
    assert "service = build_agent_service(" in cli_py
    assert "service = build_agent_service(" in tui_py
    assert "Profiles:" in cli_py


@pytest.mark.asyncio
async def test_bootstrapped_service_handles_message_and_reaction() -> None:
    service = build_agent_service()

    message_event = InboundEvent(
        event_id="evt-msg-1",
        event_type="message",
        team_id="T1",
        channel_id="C1",
        thread_ts="1.1",
        user_id="U1",
        text="/todo write docs",
    )
    message_result = await service.process_event(message_event)
    assert message_result.skill_name in {"create_task", ""}
    assert message_result.text

    reaction_event = InboundEvent(
        event_id="evt-react-1",
        event_type="reaction_added",
        team_id="T1",
        channel_id="C1",
        thread_ts="1.1",
        user_id="U1",
        reaction="eyes",
    )
    reaction_reply = await service.process_event(reaction_event)
    assert reaction_reply.skill_name in {"handle_reaction", ""}
    assert reaction_reply.text


def test_bootstrap_loads_dotenv_from_current_working_directory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("AGENT_PROVIDER", raising=False)
    monkeypatch.delenv("AGENT_MODEL", raising=False)
    monkeypatch.delenv("AGENT_API_KEY", raising=False)
    monkeypatch.delenv("AGENT_BASE_URL", raising=False)
    (tmp_path / ".env").write_text(
        "AGENT_PROVIDER=openai-compatible\n"
        "AGENT_MODEL=dotenv-model\n"
        "AGENT_API_KEY=test-key\n"
        "AGENT_BASE_URL=https://example.test/v1\n",
        encoding="utf-8",
    )

    service = build_agent_service(tools_profile="minimal")

    assert service.provider_manager is not None
    assert service.provider_manager.has_role(ROLE_AGENT)
    role_binding = service.provider_manager.settings.role_bindings[ROLE_AGENT]
    assert role_binding.endpoints[0].model == "dotenv-model"


def test_bootstrap_does_not_override_existing_environment_with_dotenv(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_PROVIDER", "openai-compatible")
    monkeypatch.setenv("AGENT_MODEL", "shell-model")
    monkeypatch.setenv("AGENT_API_KEY", "shell-key")
    monkeypatch.setenv("AGENT_BASE_URL", "https://shell.example/v1")
    (tmp_path / ".env").write_text(
        "AGENT_PROVIDER=openai-compatible\n"
        "AGENT_MODEL=dotenv-model\n"
        "AGENT_API_KEY=dotenv-key\n"
        "AGENT_BASE_URL=https://dotenv.example/v1\n",
        encoding="utf-8",
    )

    service = build_agent_service(tools_profile="minimal")

    assert service.provider_manager is not None
    role_binding = service.provider_manager.settings.role_bindings[ROLE_AGENT]
    endpoint = role_binding.endpoints[0]
    assert endpoint.model == "shell-model"
    assert endpoint.api_key == "shell-key"
    assert endpoint.base_url == "https://shell.example/v1"


def test_build_initial_state_captures_current_working_directory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    event = InboundEvent(
        event_id="evt-cwd-1",
        event_type="message",
        team_id="T1",
        channel_id="C1",
        thread_ts="1.1",
        user_id="U1",
        text="hello",
    )

    state = build_initial_state(event=event, conversation_key="T1:C1:1.1")

    assert state["runtime_working_dir"] == str(tmp_path.resolve())



