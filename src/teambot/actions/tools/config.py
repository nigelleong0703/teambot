from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from ...runtime_config import get_runtime_config_section
from .namesake import normalize_namesake_strategy
from .profiles import normalize_tool_profile


@dataclass(frozen=True)
class RuntimeToolConfig:
    profile: str
    namesake_strategy: str
    enable_echo_tool: bool
    enable_exec_alias: bool
    enable_tools: tuple[str, ...]
    disable_tools: tuple[str, ...]
    exec_timeout_seconds: int
    browser_timeout_seconds: int
    tool_output_max_chars: int


def _env_enabled(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes"}


def _to_name_tuple(raw: object) -> tuple[str, ...]:
    if not isinstance(raw, list):
        return ()
    cleaned: list[str] = []
    seen: set[str] = set()
    for item in raw:
        name = str(item or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        cleaned.append(name)
    return tuple(cleaned)


def _to_int(value: object, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _runtime_tools_section() -> dict[str, object]:
    return get_runtime_config_section("tools")


def load_runtime_tool_config(
    *,
    config_path: str | None = None,
    profile_override: str | None = None,
    strict_path: bool = False,
) -> RuntimeToolConfig:
    runtime_tools = _runtime_tools_section()
    profile = normalize_tool_profile(str(runtime_tools.get("profile") or "minimal"))
    namesake_strategy = normalize_namesake_strategy(
        str(runtime_tools.get("namesake_strategy") or "skip")
    )
    enable_echo_tool = bool(runtime_tools.get("enable_echo_tool", False))
    enable_exec_alias = bool(runtime_tools.get("enable_exec_alias", False))
    enable_tools = _to_name_tuple(runtime_tools.get("enable"))
    disable_tools = _to_name_tuple(runtime_tools.get("disable"))
    exec_timeout_seconds = _to_int(runtime_tools.get("exec_timeout_seconds"), 20)
    browser_timeout_seconds = _to_int(runtime_tools.get("browser_timeout_seconds"), 10)
    tool_output_max_chars = _to_int(runtime_tools.get("tool_output_max_chars"), 4000)

    profile = normalize_tool_profile(os.getenv("TOOLS_PROFILE", profile))
    namesake_strategy = normalize_namesake_strategy(
        os.getenv("TOOLS_NAMESAKE_STRATEGY", namesake_strategy)
    )
    if "ENABLE_ECHO_TOOL" in os.environ:
        enable_echo_tool = _env_enabled("ENABLE_ECHO_TOOL")
    if "ENABLE_EXEC_TOOL" in os.environ:
        enable_exec_alias = _env_enabled("ENABLE_EXEC_TOOL")
    if "EXEC_TIMEOUT_SECONDS" in os.environ:
        exec_timeout_seconds = _to_int(os.getenv("EXEC_TIMEOUT_SECONDS"), exec_timeout_seconds)
    if "BROWSER_TIMEOUT_SECONDS" in os.environ:
        browser_timeout_seconds = _to_int(os.getenv("BROWSER_TIMEOUT_SECONDS"), browser_timeout_seconds)
    if "TOOL_OUTPUT_MAX_CHARS" in os.environ:
        tool_output_max_chars = _to_int(os.getenv("TOOL_OUTPUT_MAX_CHARS"), tool_output_max_chars)

    if config_path:
        path = Path(config_path).expanduser().resolve()
        if not path.exists():
            if strict_path:
                raise FileNotFoundError(f"tools config file not found: {path}")
        else:
            raw = path.read_text(encoding="utf-8")
            loaded = json.loads(raw)
            if not isinstance(loaded, dict):
                raise ValueError("tools config must be a JSON object")

            cfg_profile = loaded.get("profile")
            if isinstance(cfg_profile, str):
                profile = normalize_tool_profile(cfg_profile)

            cfg_strategy = loaded.get("namesake_strategy")
            if isinstance(cfg_strategy, str):
                namesake_strategy = normalize_namesake_strategy(cfg_strategy)

            extras = loaded.get("extras")
            if isinstance(extras, dict):
                if isinstance(extras.get("enable_echo_tool"), bool):
                    enable_echo_tool = extras["enable_echo_tool"]
                if isinstance(extras.get("enable_exec_alias"), bool):
                    enable_exec_alias = extras["enable_exec_alias"]

            overrides = loaded.get("overrides")
            if isinstance(overrides, dict):
                enable_tools = _to_name_tuple(overrides.get("enable"))
                disable_tools = _to_name_tuple(overrides.get("disable"))

            if isinstance(extras, dict):
                exec_timeout_seconds = _to_int(
                    extras.get("exec_timeout_seconds"),
                    exec_timeout_seconds,
                )
                browser_timeout_seconds = _to_int(
                    extras.get("browser_timeout_seconds"),
                    browser_timeout_seconds,
                )
                tool_output_max_chars = _to_int(
                    extras.get("tool_output_max_chars"),
                    tool_output_max_chars,
                )

    if profile_override:
        profile = normalize_tool_profile(profile_override)

    return RuntimeToolConfig(
        profile=profile,
        namesake_strategy=namesake_strategy,
        enable_echo_tool=enable_echo_tool,
        enable_exec_alias=enable_exec_alias,
        enable_tools=enable_tools,
        disable_tools=disable_tools,
        exec_timeout_seconds=exec_timeout_seconds,
        browser_timeout_seconds=browser_timeout_seconds,
        tool_output_max_chars=tool_output_max_chars,
    )


def load_runtime_tool_limits() -> tuple[int, int, int]:
    cfg = load_runtime_tool_config()
    return (
        cfg.exec_timeout_seconds,
        cfg.browser_timeout_seconds,
        cfg.tool_output_max_chars,
    )
