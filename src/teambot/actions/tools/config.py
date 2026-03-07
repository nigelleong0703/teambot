from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

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


def load_runtime_tool_config(
    *,
    config_path: str | None = None,
    profile_override: str | None = None,
    strict_path: bool = False,
) -> RuntimeToolConfig:
    profile = normalize_tool_profile(os.getenv("TOOLS_PROFILE", "minimal"))
    namesake_strategy = normalize_namesake_strategy(
        os.getenv("TOOLS_NAMESAKE_STRATEGY", "skip")
    )
    enable_echo_tool = _env_enabled("ENABLE_ECHO_TOOL")
    enable_exec_alias = _env_enabled("ENABLE_EXEC_TOOL")
    enable_tools: tuple[str, ...] = ()
    disable_tools: tuple[str, ...] = ()

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

    if profile_override:
        profile = normalize_tool_profile(profile_override)

    return RuntimeToolConfig(
        profile=profile,
        namesake_strategy=namesake_strategy,
        enable_echo_tool=enable_echo_tool,
        enable_exec_alias=enable_exec_alias,
        enable_tools=enable_tools,
        disable_tools=disable_tools,
    )
