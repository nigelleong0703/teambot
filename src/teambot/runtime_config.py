from __future__ import annotations

import json
import os
from pathlib import Path
import re
from typing import Any


class RuntimeConfigError(RuntimeError):
    pass


_ENV_TEMPLATE_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")
_ESCAPED_TEMPLATE_SENTINEL = "__TEAMBOT_ESCAPED_ENV_TEMPLATE__"


def resolve_runtime_config_path() -> Path | None:
    raw = os.getenv("RUNTIME_CONFIG_FILE", "").strip()
    if raw:
        path = Path(raw).expanduser()
        if not path.is_absolute():
            path = (Path.cwd() / path).resolve()
        return path
    return None


def load_runtime_config() -> dict[str, Any]:
    path = resolve_runtime_config_path()
    if path is None:
        return {}

    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise RuntimeConfigError(f"runtime config file not found: {path}") from exc
    except OSError as exc:
        raise RuntimeConfigError(f"runtime config could not be read: {path}") from exc

    try:
        loaded = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeConfigError(f"runtime config is invalid JSON: {path}") from exc
    if not isinstance(loaded, dict):
        raise RuntimeConfigError(f"runtime config must be a JSON object: {path}")
    expanded = _expand_env_templates(loaded)
    if not isinstance(expanded, dict):
        raise RuntimeConfigError(f"runtime config must be a JSON object: {path}")
    return expanded


def get_runtime_config_section(name: str) -> dict[str, Any]:
    raw = load_runtime_config().get(name)
    if isinstance(raw, dict):
        return raw
    return {}


def _expand_env_templates(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _expand_env_templates(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_expand_env_templates(item) for item in value]
    if isinstance(value, str):
        return _expand_env_string(value)
    return value


def _expand_env_string(value: str) -> str:
    escaped = value.replace("$${", f"{_ESCAPED_TEMPLATE_SENTINEL}{{")

    def _replace(match: re.Match[str]) -> str:
        env_name = match.group(1)
        env_value = os.getenv(env_name)
        if env_value is None:
            raise RuntimeConfigError(f"runtime config references missing env var: {env_name}")
        return env_value

    expanded = _ENV_TEMPLATE_PATTERN.sub(_replace, escaped)
    return expanded.replace(f"{_ESCAPED_TEMPLATE_SENTINEL}{{", "${")
