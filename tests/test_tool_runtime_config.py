import json

from teambot.actions.tools.config import load_runtime_tool_config


def test_load_runtime_tool_config_from_json(tmp_path) -> None:
    config_path = tmp_path / "tools.json"
    config_path.write_text(
        json.dumps(
            {
                "profile": "external_operation",
                "namesake_strategy": "rename",
                "overrides": {
                    "enable": ["desktop_screenshot"],
                    "disable": ["execute_shell_command"],
                },
                "extras": {
                    "enable_echo_tool": True,
                    "enable_exec_alias": False,
                },
            }
        ),
        encoding="utf-8",
    )

    cfg = load_runtime_tool_config(config_path=str(config_path), strict_path=True)

    assert cfg.profile == "external_operation"
    assert cfg.namesake_strategy == "rename"
    assert cfg.enable_echo_tool is True
    assert cfg.enable_exec_alias is False
    assert cfg.enable_tools == ("desktop_screenshot",)
    assert cfg.disable_tools == ("execute_shell_command",)


def test_missing_strict_tools_config_raises(tmp_path) -> None:
    missing = tmp_path / "missing.json"
    try:
        load_runtime_tool_config(config_path=str(missing), strict_path=True)
        assert False, "Expected FileNotFoundError"
    except FileNotFoundError:
        assert True


def test_load_runtime_tool_config_from_runtime_config_file(monkeypatch, tmp_path) -> None:
    runtime_config = tmp_path / "config.json"
    runtime_config.write_text(
        json.dumps(
            {
                "tools": {
                    "profile": "external_operation",
                    "namesake_strategy": "rename",
                    "enable_echo_tool": True,
                    "enable_exec_alias": True,
                    "enable": ["desktop_screenshot"],
                    "disable": ["execute_shell_command"],
                    "exec_timeout_seconds": 33,
                    "browser_timeout_seconds": 44,
                    "tool_output_max_chars": 555,
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("RUNTIME_CONFIG_FILE", str(runtime_config))

    cfg = load_runtime_tool_config()

    assert cfg.profile == "external_operation"
    assert cfg.namesake_strategy == "rename"
    assert cfg.enable_echo_tool is True
    assert cfg.enable_exec_alias is True
    assert cfg.enable_tools == ("desktop_screenshot",)
    assert cfg.disable_tools == ("execute_shell_command",)
    assert cfg.exec_timeout_seconds == 33
    assert cfg.browser_timeout_seconds == 44
    assert cfg.tool_output_max_chars == 555
