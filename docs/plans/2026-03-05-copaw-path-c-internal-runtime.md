# CoPaw Path C Internal Runtime Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refactor TeamBot internals to mirror CoPaw-style runtime management for tools, skills, and MCP without changing external API/CLI behavior.

**Architecture:** Introduce a dedicated runtime orchestrator that assembles skill registry, profile-driven tool registry, and MCP-injected tools into a single action surface consumed by existing Agent Core graph. Keep request loop and public endpoints unchanged while replacing assembly internals with deterministic profile and namesake strategy mechanics.

**Tech Stack:** Python 3.10+, FastAPI, existing TeamBot Agent Core, pytest, OpenSpec.

---

Execution discipline: `@superpowers:test-driven-development`, `@superpowers:verification-before-completion`.

### Task 1: Add Tool Profile and Namesake Core

**Files:**
- Create: `src/teambot/agents/tools/profiles.py`
- Create: `src/teambot/agents/tools/namesake.py`
- Test: `tests/test_tool_profiles_and_namesake.py`

**Step 1: Write the failing test**

```python
def test_namesake_skip_keeps_first():
    merged = merge_tools(
        base={"read_file": object()},
        incoming={"read_file": object()},
        strategy="skip",
    )
    assert list(merged.keys()) == ["read_file"]
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_tool_profiles_and_namesake.py::test_namesake_skip_keeps_first -v`  
Expected: FAIL (`ImportError` or `NameError` for missing module/function).

**Step 3: Write minimal implementation**

```python
def merge_tools(base, incoming, strategy):
    out = dict(base)
    for name, value in incoming.items():
        if name not in out:
            out[name] = value
            continue
        if strategy == "skip":
            continue
    return out
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_tool_profiles_and_namesake.py::test_namesake_skip_keeps_first -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add src/teambot/agents/tools/profiles.py src/teambot/agents/tools/namesake.py tests/test_tool_profiles_and_namesake.py
git commit -m "refactor: add tool profile and namesake strategy core"
```

### Task 2: Build Runtime Tool Catalog and Builder

**Files:**
- Create: `src/teambot/agents/tools/catalog.py`
- Create: `src/teambot/agents/tools/runtime_builder.py`
- Modify: `src/teambot/agents/tools/builtin.py`
- Test: `tests/test_tool_runtime_builder.py`

**Step 1: Write the failing test**

```python
def test_external_operation_profile_includes_shell_and_file_tools():
    registry = build_runtime_tool_registry(profile="external_operation")
    names = {m.name for m in registry.list_manifests()}
    assert {"message_reply", "read_file", "write_file", "execute_shell_command"}.issubset(names)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_tool_runtime_builder.py::test_external_operation_profile_includes_shell_and_file_tools -v`  
Expected: FAIL (builder/profile unresolved).

**Step 3: Write minimal implementation**

```python
def build_runtime_tool_registry(profile: str) -> ToolRegistry:
    registry = ToolRegistry()
    for manifest, handler in resolve_profile_tools(profile):
        registry.register(manifest, handler)
    return registry
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_tool_runtime_builder.py::test_external_operation_profile_includes_shell_and_file_tools -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add src/teambot/agents/tools/catalog.py src/teambot/agents/tools/runtime_builder.py src/teambot/agents/tools/builtin.py tests/test_tool_runtime_builder.py
git commit -m "refactor: build runtime tool registry from explicit profiles"
```

### Task 3: Align Skills Lifecycle to Active-Only Runtime Loading

**Files:**
- Modify: `src/teambot/agents/skills/manager.py`
- Modify: `src/teambot/agents/core/service.py`
- Test: `tests/test_skill_runtime_lifecycle.py`

**Step 1: Write the failing test**

```python
def test_runtime_uses_active_skills_only(tmp_path, monkeypatch):
    # setup builtin/customized/active dirs with only one active skill
    manifests = load_runtime_skill_manifests()
    assert manifests == ["active_skill_only"]
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_skill_runtime_lifecycle.py::test_runtime_uses_active_skills_only -v`  
Expected: FAIL (current behavior not strictly active-only).

**Step 3: Write minimal implementation**

```python
def list_runtime_skill_names() -> list[str]:
    active_dir = get_active_skills_dir()
    return sorted(n for n in list_available_skills() if (active_dir / n / "SKILL.md").exists())
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_skill_runtime_lifecycle.py::test_runtime_uses_active_skills_only -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add src/teambot/agents/skills/manager.py src/teambot/agents/core/service.py tests/test_skill_runtime_lifecycle.py
git commit -m "refactor: enforce active-only skill loading in runtime"
```

### Task 4: Add MCP Manager and Registry Bridge

**Files:**
- Create: `src/teambot/agents/mcp/config.py`
- Create: `src/teambot/agents/mcp/manager.py`
- Create: `src/teambot/agents/mcp/bridge.py`
- Test: `tests/test_mcp_runtime_bridge.py`

**Step 1: Write the failing test**

```python
def test_mcp_bridge_registers_tools_as_manifests():
    tools = [MockTool(name="mcp_search")]
    registry = ToolRegistry()
    register_mcp_tools(registry, tools)
    assert registry.has("mcp_search")
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_mcp_runtime_bridge.py::test_mcp_bridge_registers_tools_as_manifests -v`  
Expected: FAIL (`register_mcp_tools` missing).

**Step 3: Write minimal implementation**

```python
def register_mcp_tools(registry: ToolRegistry, tools: list[McpTool]) -> None:
    for tool in tools:
        registry.register(
            ToolManifest(name=tool.name, description=tool.description, risk_level="low"),
            tool.invoke,
        )
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_mcp_runtime_bridge.py::test_mcp_bridge_registers_tools_as_manifests -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add src/teambot/agents/mcp/config.py src/teambot/agents/mcp/manager.py src/teambot/agents/mcp/bridge.py tests/test_mcp_runtime_bridge.py
git commit -m "feat: add mcp runtime manager and tool bridge"
```

### Task 5: Introduce Runtime Orchestrator

**Files:**
- Create: `src/teambot/agents/runtime/orchestrator.py`
- Modify: `src/teambot/agents/core/service.py`
- Modify: `src/teambot/interfaces/bootstrap.py`
- Test: `tests/test_runtime_orchestrator.py`

**Step 1: Write the failing test**

```python
def test_orchestrator_builds_runtime_components():
    runtime = RuntimeOrchestrator().build()
    assert runtime.skill_registry is not None
    assert runtime.tool_registry is not None
    assert runtime.plugin_host is not None
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_runtime_orchestrator.py::test_orchestrator_builds_runtime_components -v`  
Expected: FAIL (`RuntimeOrchestrator` missing).

**Step 3: Write minimal implementation**

```python
@dataclass
class RuntimeBundle:
    skill_registry: SkillRegistry
    tool_registry: ToolRegistry
    plugin_host: PluginHost

class RuntimeOrchestrator:
    def build(self) -> RuntimeBundle:
        ...
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_runtime_orchestrator.py::test_orchestrator_builds_runtime_components -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add src/teambot/agents/runtime/orchestrator.py src/teambot/agents/core/service.py src/teambot/interfaces/bootstrap.py tests/test_runtime_orchestrator.py
git commit -m "refactor: centralize runtime assembly in orchestrator"
```

### Task 6: Wire Environment Contract and Update Docs

**Files:**
- Modify: `.env.template`
- Modify: `docs/agent-core-algorithm.md`
- Modify: `repo_wiki.md`

**Step 1: Write the failing test**

```python
def test_env_template_contains_runtime_profile_keys():
    text = Path(".env.template").read_text(encoding="utf-8")
    assert "TOOLS_PROFILE=" in text
    assert "TOOLS_NAMESAKE_STRATEGY=" in text
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_interface_parity.py::test_env_template_contains_runtime_profile_keys -v`  
Expected: FAIL (key missing).

**Step 3: Write minimal implementation**

```text
TOOLS_PROFILE=external_operation
TOOLS_NAMESAKE_STRATEGY=skip
MCP_ENABLED=false
MCP_CONFIG_PATH=
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_interface_parity.py::test_env_template_contains_runtime_profile_keys -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add .env.template docs/agent-core-algorithm.md repo_wiki.md tests/test_interface_parity.py
git commit -m "docs: align env and runtime docs with copaw style internals"
```

### Task 7: End-to-End Verification and Spec Sync

**Files:**
- Modify: `openspec/specs/builtin-open-tools-parity/spec.md` (if requirement wording changed)
- Modify: `openspec/specs/skills-tool-orchestration/spec.md` (if requirement wording changed)

**Step 1: Write the failing test**

```python
def test_reload_runtime_preserves_request_processing():
    service = AgentService()
    service.reload_runtime()
    assert service.graph is not None
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_react_loop.py::test_reload_runtime_preserves_request_processing -v`  
Expected: FAIL before final wiring.

**Step 3: Write minimal implementation**

```python
def reload_runtime(self) -> None:
    bundle = self._orchestrator.build()
    self.registry = bundle.skill_registry
    self.tool_registry = bundle.tool_registry
    self.plugin_host = bundle.plugin_host
    self.graph = build_graph(...)
```

**Step 4: Run test to verify it passes**

Run:
- `pytest -q`
- `openspec validate --specs`

Expected:
- pytest all green
- OpenSpec specs validation pass

**Step 5: Commit**

```bash
git add src/teambot/agents/core/service.py tests/test_react_loop.py openspec/specs/builtin-open-tools-parity/spec.md openspec/specs/skills-tool-orchestration/spec.md
git commit -m "refactor: complete copaw-style internal runtime assembly"
```

### Task 8: Final Review Gate

**Files:**
- Modify: `openspec/changes/archive/2026-03-05-align-open-tools-with-copaw-baseline/*` (only if required for trace notes)

**Step 1: Write the failing test**

```python
def test_no_open_items_left():
    assert True
```

**Step 2: Run verification to confirm no regressions**

Run:
- `pytest -q`
- `openspec validate --specs`
- `git status --short`

Expected:
- tests pass
- specs pass
- only intended files changed

**Step 3: Produce release notes draft**

```text
- Internal runtime now uses profile-driven tool assembly.
- Skills runtime uses active-only loading semantics.
- MCP tools can be bridged into the same action surface.
```

**Step 4: Confirm rollback instructions exist**

Run: `Select-String -Path docs/plans/2026-03-05-copaw-path-c-internal-runtime-design.md -Pattern "Rollback"`  
Expected: at least one match.

**Step 5: Commit**

```bash
git add docs/plans/2026-03-05-copaw-path-c-internal-runtime-design.md docs/plans/2026-03-05-copaw-path-c-internal-runtime.md
git commit -m "docs: add execution plan for copaw path c internal runtime"
```

