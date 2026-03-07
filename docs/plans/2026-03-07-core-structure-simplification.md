# Core Structure Simplification Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reduce `agents/core` to the files that map directly to the ReAct loop so engineers know where to make behavior changes.

**Architecture:** Move the application service out of `agents/core`, rename the decision and execution modules to match their responsibilities, and merge state helpers into the execution module. Keep runtime behavior unchanged; this is a structural refactor plus documentation refresh.

**Tech Stack:** Python, pytest, Pydantic

---

### Task 1: Lock the target structure with tests

**Files:**
- Create: `tests/test_core_structure.py`

**Step 1: Write the failing test**

Assert that:
- `src/teambot/agents/core/reason.py` exists
- `src/teambot/agents/core/execution.py` exists
- `src/teambot/agents/service.py` exists
- `src/teambot/agents/core/router.py` does not exist
- `src/teambot/agents/core/executor.py` does not exist
- `src/teambot/agents/core/action_state.py` does not exist
- `src/teambot/agents/core/service.py` does not exist

**Step 2: Run test to verify it fails**

Run: `pytest -q tests/test_core_structure.py`

Expected: FAIL because the old files still exist and the new files do not.

### Task 2: Restructure the core modules

**Files:**
- Create: `src/teambot/agents/core/reason.py`
- Create: `src/teambot/agents/core/execution.py`
- Create: `src/teambot/agents/service.py`
- Modify: `src/teambot/agents/core/graph.py`
- Modify: `src/teambot/agents/core/__init__.py`
- Modify: `src/teambot/agents/react_agent.py`
- Modify: `src/teambot/app/bootstrap.py`
- Modify: `src/teambot/app/cli.py`
- Delete: `src/teambot/agents/core/router.py`
- Delete: `src/teambot/agents/core/executor.py`
- Delete: `src/teambot/agents/core/action_state.py`
- Delete: `src/teambot/agents/core/service.py`

**Step 1: Move logic without changing runtime behavior**

- `router.py` -> `reason.py`
- `executor.py` + `action_state.py` -> `execution.py`
- `core/service.py` -> `agents/service.py`
- Update imports to the new locations

**Step 2: Run focused tests**

Run: `pytest -q tests/test_core_structure.py tests/test_react_loop.py tests/test_routing.py tests/test_interface_parity.py`

Expected: PASS

### Task 3: Refresh docs to match the new entry points

**Files:**
- Modify: `docs/README.md`
- Modify: `docs/code-structure.md`
- Modify: `docs/agent-core-algorithm.md`
- Modify: `repo_wiki.md`

**Step 1: Update runtime/file references**

- `agents/core` should document `graph.py`, `reason.py`, `execution.py`, `state.py`
- `AgentService` should point to `src/teambot/agents/service.py`
- Remove stale `router.py`, `executor.py`, `action_state.py`, `core/service.py` references

**Step 2: Run full verification**

Run: `pytest -q`

Expected: PASS
