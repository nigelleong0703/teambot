# Runtime To Agent Rename Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rename the core package from `agent/` to `agent/` so the repository reflects that this directory is the agent core while keeping `actions/providers/skills/mcp/contracts/app` unchanged.

**Architecture:** Move the current `runtime` package to `agent`, update all imports and package exports, and refresh canonical docs so `agent/` is the only name used for the core loop and runtime owner. Behavior stays the same; this is a naming and path migration.

**Tech Stack:** Python, pytest, Pydantic

---

### Task 1: Lock the new package naming with tests

**Files:**
- Modify: `tests/test_core_structure.py`

**Step 1: Write the failing test**

Assert that:
- `src/teambot/agent/graph.py` exists
- `src/teambot/agent/reason.py` exists
- `src/teambot/agent/execution.py` exists
- `src/teambot/agent/state.py` exists
- `src/teambot/agent/policy.py` exists
- `src/teambot/agent/runtime.py` exists
- `src/teambot/agent/service.py` exists
- `src/teambot/agent/orchestrator.py` exists
- `src/teambot/agent/prompts/system_prompt.py` exists
- `src/teambot/agent/` does not exist

**Step 2: Run test to verify it fails**

Run: `pytest -q tests/test_core_structure.py`

Expected: FAIL because the package is still named `agent/`.

### Task 2: Rename the package and update imports

**Files:**
- Create: `src/teambot/agent/*`
- Modify: `src/teambot/app/*.py`
- Modify: `src/teambot/actions/*`
- Modify: `src/teambot/providers/*`
- Modify: `src/teambot/skills/*`
- Modify: `src/teambot/mcp/*`
- Modify: `tests/*`
- Delete: `src/teambot/agent/*`

**Step 1: Move code without changing behavior**

- `runtime/*` -> `agent/*`
- `runtime/prompts/*` -> `agent/prompts/*`
- update imports from `teambot.agent.*` to `teambot.agent.*`
- keep the rest of the top-level structure unchanged

**Step 2: Run focused regression tests**

Run: `pytest -q tests/test_core_structure.py tests/test_react_loop.py tests/test_routing.py tests/test_provider_manager.py tests/test_skill_lifecycle.py tests/test_mcp_runtime_bridge.py tests/test_interface_parity.py`

Expected: PASS

### Task 3: Align docs with the new canonical name

**Files:**
- Modify: `docs/code-structure.md`
- Modify: `docs/architecture-boundaries.md`
- Modify: `docs/agent-core-algorithm.md`
- Modify: `docs/README.md`
- Modify: `docs/modules/project-overview.md`
- Modify: `repo_wiki.md`

**Step 1: Replace `agent/` references with `agent/` where they refer to the core package**

Keep:
- `actions/`
- `providers/`
- `skills/`
- `mcp/`
- `contracts/`
- `app/`

**Step 2: Run full verification**

Run: `pytest -q`

Expected: PASS
