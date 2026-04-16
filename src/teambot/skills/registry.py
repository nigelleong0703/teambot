"""Plugin-based skill registry.

Skills register themselves by calling ``skill_registry.register()`` from their
``__init__.py``.  The registry discovers new packages at call time via
``discover(directory)`` — no cold loading, no restart required.
"""
from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SkillManifest:
    name: str
    description: str = ""
    when_to_use: str = ""


@dataclass(frozen=True)
class RegisteredSkill:
    manifest: SkillManifest
    content: str


class SkillRegistry:
    def __init__(self) -> None:
        self._skills: dict[str, RegisteredSkill] = {}
        self._discovered: set[str] = set()

    def register(self, manifest: SkillManifest, *, content: str = "") -> None:
        self._skills[manifest.name] = RegisteredSkill(manifest=manifest, content=content)

    def unregister(self, name: str) -> bool:
        if name not in self._skills:
            return False
        del self._skills[name]
        return True

    def get(self, name: str) -> RegisteredSkill | None:
        return self._skills.get(name)

    def list_all(self) -> list[RegisteredSkill]:
        return sorted(self._skills.values(), key=lambda s: s.manifest.name)

    def discover(self, directory: Path) -> None:
        """Import skill plugin packages in directory that have not yet been loaded.

        Each package must contain an ``__init__.py`` that calls
        ``skill_registry.register(...)``.  Already-imported packages are skipped,
        so this method is safe to call on every request.
        """
        if not directory.is_dir():
            return
        for item in sorted(directory.iterdir()):
            if not item.is_dir():
                continue
            init_py = item / "__init__.py"
            if not init_py.exists():
                continue
            key = str(item.resolve())
            if key in self._discovered:
                continue
            self._discovered.add(key)
            module_name = f"_teambot_skill_{item.name}"
            spec = importlib.util.spec_from_file_location(module_name, init_py)
            if spec is None or spec.loader is None:
                self._discovered.discard(key)
                continue
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            try:
                spec.loader.exec_module(module)  # type: ignore[union-attr]
            except Exception:
                sys.modules.pop(module_name, None)
                self._discovered.discard(key)


# Module-level singleton shared by all skill plugins.
skill_registry = SkillRegistry()
