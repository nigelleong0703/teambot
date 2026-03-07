# Runtime Loop Simplification Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Simplify TeamBot runtime control flow so the loop continues based on model tool calls instead of custom follow-up/continuation signals.

**Architecture:** Keep the conceptual `reason -> act -> observe -> compose_reply` loop, but remove follow-up routing and executable-skill continuation semantics from the implementation. Skills become context-only again, deterministic event handlers stay as thin pre-routing, and ordinary multi-step work flows through repeated model tool calls.

**Tech Stack:** Python 3.10+, existing TeamBot Agent Core, pytest.

---

Execution discipline: `@superpowers:test-driven-development`, `@superpowers:verification-before-completion`.

### Task 1: Lock Down Simplified Loop Semantics in Tests

**Files:**
- Modify: `tests/test_react_loop.py`
- Modify: `tests/test_reasoner_skill_context.py`
- Modify: `tests/test_planner_integration.py`

**Step 1: Write the failing test**

```python
def test_react_graph_continues_when_reasoner_emits_second_tool_call() -> None:
    result = graph.invoke(state)
    assert result["execution_trace"][0]["action"] == "first"
    assert result["execution_trace"][1]["action"] == "second"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_react_loop.py::test_react_graph_continues_when_reasoner_emits_second_tool_call -v`
Expected: FAIL because current runtime depends on follow-up continuation fields.

**Step 3: Write minimal implementation**

```python
# No production implementation in this task.
```

**Step 4: Run targeted failing tests**

Run:
- `pytest tests/test_react_loop.py -q`
- `pytest tests/test_reasoner_skill_context.py -q`
- `pytest tests/test_planner_integration.py -q`

Expected: new assertions fail for follow-up-free loop semantics.

**Step 5: Commit**

```bash
git add tests/test_react_loop.py tests/test_reasoner_skill_context.py tests/test_planner_integration.py
git commit -m "test: lock down simplified runtime loop semantics"
```

### Task 2: Remove Follow-Up Routing and Continuation Signals

**Files:**
- Modify: `src/teambot/agents/core/router.py`
- Modify: `src/teambot/agents/core/executor.py`
- Modify: `src/teambot/agents/core/graph.py`

**Step 1: Write the failing test**

```python
def test_observe_only_marks_done_after_final_text() -> None:
    output = observe_node(state_with_tool_result)
    assert output["react_done"] is False
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_react_loop.py::test_observe_only_marks_done_after_final_text -v`
Expected: FAIL because `observe_node` currently stops when no follow-up signal is emitted.

**Step 3: Write minimal implementation**

```python
def observe_node(state: AgentState) -> dict:
    return {
        "react_step": step,
        "react_done": False,
        ...
    }
```

**Step 4: Run test to verify it passes**

Run:
- `pytest tests/test_react_loop.py -q`
- `pytest tests/test_planner_integration.py -q`

Expected: PASS with router no longer consulting follow-up continuation fields.

**Step 5: Commit**

```bash
git add src/teambot/agents/core/router.py src/teambot/agents/core/executor.py src/teambot/agents/core/graph.py tests/test_react_loop.py tests/test_planner_integration.py
git commit -m "refactor: simplify runtime loop continuation"
```

### Task 3: Demote Skills Back to Context-Only Runtime Data

**Files:**
- Modify: `src/teambot/skills/runtime_loader.py`
- Modify: `src/teambot/skills/context.py`
- Modify: `tests/test_reasoner_skill_context.py`
- Modify: `tests/test_skill_lifecycle.py`

**Step 1: Write the failing test**

```python
def test_reasoner_tool_schema_excludes_skills() -> None:
    names = [tool.name for tool in probe.tools_seen]
    assert "browser_visible" not in names
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_reasoner_skill_context.py::test_reasoner_tool_schema_excludes_skills -v`
Expected: FAIL because active skill docs are currently registered as executable skill actions.

**Step 3: Write minimal implementation**

```python
def build_runtime_skill_registry(...):
    return SkillRegistry()
```

**Step 4: Run test to verify it passes**

Run:
- `pytest tests/test_reasoner_skill_context.py -q`
- `pytest tests/test_skill_lifecycle.py -q`

Expected: PASS with skills only appearing in reasoner context, not tool schema or execution.

**Step 5: Commit**

```bash
git add src/teambot/skills/runtime_loader.py src/teambot/skills/context.py tests/test_reasoner_skill_context.py tests/test_skill_lifecycle.py
git commit -m "refactor: keep skills as context only"
```

### Task 4: Update Runtime Documentation

**Files:**
- Modify: `docs/agent-core-algorithm.md`
- Modify: `docs/README.md`
- Modify: `docs/code-structure.md`
- Modify: `repo_wiki.md`

**Step 1: Write the failing test**

```python
def test_agent_core_algorithm_mentions_no_follow_up_protocol():
    text = Path("docs/agent-core-algorithm.md").read_text(encoding="utf-8")
    assert "follow-up route" not in text.lower()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_interface_parity.py::test_agent_core_algorithm_mentions_no_follow_up_protocol -v`
Expected: FAIL because docs still describe `next_action`, `next_skill`, and `continue_reasoning`.

**Step 3: Write minimal implementation**

```text
Reason stage returns either final text or a tool call.
Observe records tool results and returns control to the next reason step.
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_interface_parity.py::test_agent_core_algorithm_mentions_no_follow_up_protocol -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add docs/agent-core-algorithm.md docs/README.md docs/code-structure.md repo_wiki.md tests/test_interface_parity.py
git commit -m "docs: align runtime docs with simplified loop"
```

### Task 5: Verification

**Files:**
- Modify: none unless verification exposes gaps

**Step 1: Run targeted verification**

Run:
- `pytest tests/test_react_loop.py -q`
- `pytest tests/test_reasoner_skill_context.py -q`
- `pytest tests/test_skill_lifecycle.py -q`

Expected: PASS.

**Step 2: Run full verification**

Run: `pytest -q`
Expected: full suite PASS.

**Step 3: Check documentation drift**

Run: `git diff -- docs/agent-core-algorithm.md docs/README.md docs/code-structure.md repo_wiki.md`
Expected: docs reflect loop simplification and no stale continuation language remains.

**Step 4: Confirm changed files are scoped**

Run: `git status --short`
Expected: only intended runtime/tests/docs files are changed in this task.

**Step 5: Commit**

```bash
git add docs/plans/2026-03-06-runtime-loop-simplification.md
git commit -m "docs: add runtime loop simplification plan"
```
