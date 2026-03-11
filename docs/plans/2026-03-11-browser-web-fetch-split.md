# Browser And Web Fetch Split Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the misleading `browser_use` fetch tool with a separate `web_fetch` tool and add a minimal OpenClaw-style `browser(action=...)` interaction surface.

**Architecture:** Keep `web_fetch` as a narrow stateless HTTP retrieval tool, and add a separate stateful `browser` tool for interactive workflows. Update runtime registration, tests, and docs together so the tool split is reflected consistently across the runtime surface.

**Tech Stack:** Python 3.11, urllib, pytest

---

### Task 1: Add failing tests for the new tool surface

**Files:**
- Modify: `tests/test_tool_runtime_builder.py`
- Modify: `tests/test_external_operation_tools.py`
- Modify: `tests/test_reason_prompt.py`

**Step 1: Write the failing tests**

Add tests that assert:
- `external_operation` registers `web_fetch` and `browser`
- `browser_use` is no longer the primary registered tool in that profile
- reasoner-facing tool copy mentions URL retrieval via `web_fetch` and interaction via `browser`

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_tool_runtime_builder.py tests/test_external_operation_tools.py tests/test_reason_prompt.py`

Expected: FAIL because the current runtime still exposes `browser_use` only.

**Step 3: Write minimal implementation**

Update manifests/profile order and prompt copy just enough for the tests to pass.

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_tool_runtime_builder.py tests/test_external_operation_tools.py tests/test_reason_prompt.py`

Expected: PASS

### Task 2: Add failing tests for `web_fetch`

**Files:**
- Modify: `tests/test_external_operation_tools.py`
- Modify: `src/teambot/actions/tools/catalog.py`

**Step 1: Write the failing tests**

Add tests that assert:
- `web_fetch` requires `url`
- `web_fetch` returns fetched content metadata
- `web_fetch` respects optional `timeout_seconds` and `max_chars`

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_external_operation_tools.py -k web_fetch`

Expected: FAIL because `web_fetch` does not exist yet.

**Step 3: Write minimal implementation**

Implement `web_fetch` as the narrow HTTP retrieval tool and register its schema/description.

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_external_operation_tools.py -k web_fetch`

Expected: PASS

### Task 3: Add failing tests for minimal `browser(action=...)`

**Files:**
- Modify: `tests/test_external_operation_tools.py`
- Modify: `src/teambot/actions/tools/catalog.py`

**Step 1: Write the failing tests**

Add tests that assert:
- `browser` requires an `action`
- unsupported actions return a clear error
- the initial minimal action set is described in schema/manifest text
- non-interactive fetch behavior is no longer attached to `browser`

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_external_operation_tools.py -k browser`

Expected: FAIL because the runtime still uses the old fetch-style `browser_use`.

**Step 3: Write minimal implementation**

Implement a minimal `browser` handler boundary with explicit action dispatch and clear placeholder responses for the supported first-pass actions.

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_external_operation_tools.py -k browser`

Expected: PASS

### Task 4: Update docs and runtime references

**Files:**
- Modify: `docs/agent-core-algorithm.md`
- Modify: `docs/modules/project-overview.md`
- Modify: `docs/modules/post-change-next-steps.md`
- Modify: `docs/README.md`
- Modify: `docs/code-structure.md`
- Modify: `repo_wiki.md`

**Step 1: Write the doc updates**

Update canonical docs so they describe:
- `web_fetch` as the URL retrieval tool
- `browser` as the interactive browser tool
- the old `browser_use` wording removed or explicitly marked legacy if still temporarily referenced

**Step 2: Verify docs are accurate against code**

Run:

```bash
rg -n "browser_use|web_fetch|browser" docs repo_wiki.md src/teambot
```

Expected: canonical docs reflect the new split without stale primary references to `browser_use`.

### Task 5: Run focused verification

**Files:**
- Test: `tests/test_tool_runtime_builder.py`
- Test: `tests/test_external_operation_tools.py`
- Test: `tests/test_reason_prompt.py`

**Step 1: Run focused test slice**

Run:

```bash
PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_tool_runtime_builder.py tests/test_external_operation_tools.py tests/test_reason_prompt.py
```

Expected: PASS

**Step 2: Run adjacent regression slice**

Run:

```bash
PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_runtime_config.py tests/test_runtime_orchestrator.py tests/test_cli_modes.py
```

Expected: PASS, proving the tool split did not break runtime/tool assembly.
