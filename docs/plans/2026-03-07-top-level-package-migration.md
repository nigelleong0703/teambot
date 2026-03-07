# Top-Level Package Migration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Migrate TeamBot from the transitional `agent/agents/agent_core` layout to the canonical `runtime/actions/providers/skills/mcp/contracts` structure so the codebase matches `docs/code-structure.md`.

**Architecture:** Move runtime code from `agent` into `runtime`, move provider/skill/MCP packages out of `agents`, move `agent_core` contracts into `contracts`, and update imports/tests/docs in lockstep. Keep runtime behavior unchanged; this is a structural migration plus documentation alignment.

**Tech Stack:** Python, pytest, Pydantic

---

### Task 1: Lock the target package structure with tests

**Files:**
- Modify: `tests/test_core_structure.py`

**Step 1: Write the failing test**

Assert that:
- `src/teambot/runtime/graph.py` exists
- `src/teambot/runtime/reason.py` exists
- `src/teambot/runtime/execution.py` exists
- `src/teambot/runtime/runtime.py` exists
- `src/teambot/runtime/service.py` exists
- `src/teambot/providers/manager.py` exists
- `src/teambot/skills/manager.py` exists
- `src/teambot/mcp/manager.py` exists
- `src/teambot/contracts/contracts.py` exists
- `src/teambot/runtime/` does not exist
- `src/teambot/providers/` does not exist
- `src/teambot/skills/` does not exist
- `src/teambot/mcp/` does not exist
- `src/teambot/contracts/` does not exist

**Step 2: Run test to verify it fails**

Run: `pytest -q tests/test_core_structure.py`

Expected: FAIL because the new package layout does not exist yet.

### Task 2: Migrate packages and imports

**Files:**
- Create: `src/teambot/runtime/*`
- Create: `src/teambot/providers/*`
- Create: `src/teambot/skills/*`
- Create: `src/teambot/mcp/*`
- Create: `src/teambot/contracts/*`
- Modify: `src/teambot/app/*.py`
- Modify: `src/teambot/actions/*`
- Modify: `src/teambot/domain/*`
- Modify: `src/teambot/__init__.py`
- Delete: `src/teambot/runtime/*`
- Delete: `src/teambot/providers/*`
- Delete: `src/teambot/skills/*`
- Delete: `src/teambot/mcp/*`
- Delete: `src/teambot/contracts/*`

**Step 1: Move code without changing behavior**

- `agent/*` -> `runtime/*`
- `agents/providers/*` -> `providers/*`
- `agents/skills/*` -> `skills/*`
- `agents/mcp/*` -> `mcp/*`
- `agent_core/*` -> `contracts/*`
- update all imports and public package exports

**Step 2: Run focused regression tests**

Run: `pytest -q tests/test_core_structure.py tests/test_react_loop.py tests/test_routing.py tests/test_provider_manager.py tests/test_skill_lifecycle.py tests/test_mcp_runtime_bridge.py`

Expected: PASS

### Task 3: Align docs with the new package names

**Files:**
- Modify: `docs/README.md`
- Modify: `docs/code-structure.md`
- Modify: `docs/architecture-boundaries.md`
- Modify: `docs/agent-core-algorithm.md`
- Modify: `docs/modules/project-overview.md`
- Modify: `docs/modules/getting-started.md`
- Modify: `repo_wiki.md`

**Step 1: Replace transitional paths with canonical paths**

- `src/teambot/runtime/*` -> `src/teambot/runtime/*`
- `src/teambot/providers/*` -> `src/teambot/providers/*`
- `src/teambot/skills/*` -> `src/teambot/skills/*`
- `src/teambot/mcp/*` -> `src/teambot/mcp/*`
- `src/teambot/contracts/*` -> `src/teambot/contracts/*`

**Step 2: Run full verification**

Run: `pytest -q`

Expected: PASS
