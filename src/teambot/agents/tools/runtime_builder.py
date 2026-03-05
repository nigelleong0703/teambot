from __future__ import annotations

from ...agent_core.contracts import ModelRoleInvoker
from .catalog import builtin_tool_definitions
from .namesake import apply_namesake_strategy, normalize_namesake_strategy
from .profiles import resolve_tool_profile
from .registry import ToolRegistry


def _ordered_profile_names(profile: str | None) -> list[str]:
    # Keep deterministic order for stable manifests/tests.
    order = [
        "message_reply",
        "read_file",
        "write_file",
        "edit_file",
        "execute_shell_command",
        "browser_use",
        "get_current_time",
        "desktop_screenshot",
        "send_file_to_user",
    ]
    selected = resolve_tool_profile(profile)
    return [name for name in order if name in selected]


def build_runtime_tool_registry(
    *,
    profile: str | None,
    provider_manager: ModelRoleInvoker | None,
    namesake_strategy: str = "skip",
    enable_echo_tool: bool = False,
    enable_exec_alias: bool = False,
) -> ToolRegistry:
    strategy = normalize_namesake_strategy(namesake_strategy)
    registry = ToolRegistry()
    definitions = builtin_tool_definitions(provider_manager)
    registered_names: set[str] = set()

    for name in _ordered_profile_names(profile):
        manifest, handler = definitions[name]
        resolved_name = apply_namesake_strategy(
            existing=registered_names,
            incoming_name=manifest.name,
            strategy=strategy,
            namespace="builtin",
        )
        if resolved_name is None:
            continue
        if resolved_name != manifest.name:
            manifest = type(manifest)(
                name=resolved_name,
                description=manifest.description,
                risk_level=manifest.risk_level,
                timeout_seconds=manifest.timeout_seconds,
            )
        registry.register(manifest, handler)
        registered_names.add(manifest.name)

    if enable_echo_tool:
        manifest, handler = definitions["tool_echo"]
        registry.register(manifest, handler)

    if enable_exec_alias:
        manifest, handler = definitions["exec_command"]
        if not registry.has(manifest.name):
            registry.register(manifest, handler)

    return registry
