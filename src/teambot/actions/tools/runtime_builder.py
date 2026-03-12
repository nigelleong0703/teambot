from __future__ import annotations

from ...contracts.contracts import ModelRoleInvoker
from .catalog import builtin_tool_definitions
from .namesake import apply_namesake_strategy, normalize_namesake_strategy
from .profiles import resolve_tool_profile
from .registry import ToolRegistry


def _ordered_profile_names(
    profile: str | None,
    *,
    enable_echo_tool: bool,
    enable_exec_alias: bool,
    enable_tools: tuple[str, ...] | list[str] | None,
    disable_tools: tuple[str, ...] | list[str] | None,
) -> list[str]:
    # Keep deterministic order for stable manifests/tests.
    order = [
        "activate_skill",
        "read_file",
        "write_file",
        "edit_file",
        "execute_shell_command",
        "web_fetch",
        "browser",
        "get_current_time",
        "todo_read",
        "todo_write",
        "desktop_screenshot",
        "send_file_to_user",
        "tool_echo",
        "exec_command",
    ]
    selected = resolve_tool_profile(profile)
    selected.add("activate_skill")
    if enable_echo_tool:
        selected.add("tool_echo")
    if enable_exec_alias:
        selected.add("exec_command")
    for name in (enable_tools or []):
        selected.add(name)
    for name in (disable_tools or []):
        selected.discard(name)
    return [name for name in order if name in selected]


def build_runtime_tool_registry(
    *,
    profile: str | None,
    provider_manager: ModelRoleInvoker | None,
    namesake_strategy: str = "skip",
    enable_echo_tool: bool = False,
    enable_exec_alias: bool = False,
    enable_tools: tuple[str, ...] | list[str] | None = None,
    disable_tools: tuple[str, ...] | list[str] | None = None,
) -> ToolRegistry:
    strategy = normalize_namesake_strategy(namesake_strategy)
    registry = ToolRegistry()
    definitions = builtin_tool_definitions(provider_manager)
    registered_names: set[str] = set()

    for name in _ordered_profile_names(
        profile,
        enable_echo_tool=enable_echo_tool,
        enable_exec_alias=enable_exec_alias,
        enable_tools=enable_tools,
        disable_tools=disable_tools,
    ):
        if name not in definitions:
            continue
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

    return registry
