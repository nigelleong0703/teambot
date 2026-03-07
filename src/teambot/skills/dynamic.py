from __future__ import annotations

import importlib.util
import logging
from pathlib import Path
from types import ModuleType
from typing import Any

from .registry import SkillManifest, SkillRegistry

logger = logging.getLogger(__name__)


def load_dynamic_skills(registry: SkillRegistry, skills_dir: str | Path) -> list[str]:
    """Load skill plugins from a directory.

    Plugin contract (one of):
    1) export `manifest` + `handle`
       - `manifest`: SkillManifest or dict{name, description, timeout_seconds?}
       - `handle`: callable(state) -> dict
    2) export `register(registry)` and register skill(s) manually.
    """
    root = Path(skills_dir).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        logger.warning("skills dir not found or not a directory: %s", root)
        return []

    loaded: list[str] = []
    for file_path in sorted(root.glob("*.py")):
        if file_path.name.startswith("_"):
            continue
        try:
            module = _load_module(file_path)
            names = _register_module_skills(registry=registry, module=module)
            loaded.extend(names)
        except Exception as exc:
            logger.exception("failed to load skill plugin %s: %s", file_path, exc)
    return loaded


def _load_module(file_path: Path) -> ModuleType:
    module_name = f"teambot_dynamic_skill_{file_path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module spec from {file_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _register_module_skills(registry: SkillRegistry, module: ModuleType) -> list[str]:
    if hasattr(module, "register"):
        register_func = getattr(module, "register")
        if not callable(register_func):
            raise TypeError("plugin register is not callable")
        result = register_func(registry)
        if isinstance(result, list):
            return [str(x) for x in result]
        return []

    if not hasattr(module, "manifest") or not hasattr(module, "handle"):
        raise ValueError("plugin must expose `manifest` and `handle` or `register`")

    manifest = _normalize_manifest(getattr(module, "manifest"))
    handle = getattr(module, "handle")
    if not callable(handle):
        raise TypeError("plugin handle is not callable")
    registry.register(manifest, handle)
    return [manifest.name]


def _normalize_manifest(raw: Any) -> SkillManifest:
    if isinstance(raw, SkillManifest):
        return raw
    if isinstance(raw, dict):
        name = str(raw.get("name", "")).strip()
        description = str(raw.get("description", "")).strip()
        timeout_raw = raw.get("timeout_seconds", 20)
        timeout_seconds = int(timeout_raw) if isinstance(timeout_raw, (int, float)) else 20
        if not name:
            raise ValueError("manifest.name is required")
        return SkillManifest(
            name=name,
            description=description or "Dynamic skill plugin",
            timeout_seconds=timeout_seconds,
        )
    raise TypeError("manifest must be SkillManifest or dict")
