from __future__ import annotations

from dataclasses import dataclass

from teambot.app.cli import TeamBotCli


@dataclass
class _ToolRegistryStub:
    def list_manifests(self) -> list[object]:
        return []


class _ServiceStub:
    def __init__(self) -> None:
        self.tool_registry = _ToolRegistryStub()
        self.reload_calls = 0

    def set_model_event_listener(self, _listener) -> None:
        return None

    def reload_runtime(self) -> None:
        self.reload_calls += 1


def _build_cli(service: _ServiceStub) -> TeamBotCli:
    return TeamBotCli(
        team_id="T1",
        channel_id="C1",
        thread_ts="1710000000.0001",
        user_id="U1",
        service=service,  # type: ignore[arg-type]
    )


def test_cli_skills_sync_command_triggers_reload(monkeypatch, capsys) -> None:
    from teambot.skills.manager import SkillService

    monkeypatch.setattr(
        SkillService,
        "sync_all",
        staticmethod(lambda force=False: (2, 1)),
    )
    service = _ServiceStub()
    cli = _build_cli(service)

    handled = cli._handle_command("/skills sync")

    captured = capsys.readouterr().out
    assert handled is True
    assert service.reload_calls == 1
    assert "[skills] synced=2 skipped=1" in captured


def test_cli_skills_enable_disable_commands(monkeypatch, capsys) -> None:
    from teambot.skills.manager import SkillService

    monkeypatch.setattr(SkillService, "enable_skill", staticmethod(lambda name, force=False: name == "brainstorming"))
    monkeypatch.setattr(SkillService, "disable_skill", staticmethod(lambda name: name == "brainstorming"))
    service = _ServiceStub()
    cli = _build_cli(service)

    assert cli._handle_command("/skills enable brainstorming") is True
    assert cli._handle_command("/skills disable brainstorming") is True
    captured = capsys.readouterr().out
    assert service.reload_calls == 2
    assert "[skills] enabled=brainstorming ok=True" in captured
    assert "[skills] disabled=brainstorming ok=True" in captured


def test_cli_does_not_handle_removed_tools_command(capsys) -> None:
    service = _ServiceStub()
    cli = _build_cli(service)

    handled = cli._handle_command("/tools")

    assert handled is False
    assert capsys.readouterr().out == ""

