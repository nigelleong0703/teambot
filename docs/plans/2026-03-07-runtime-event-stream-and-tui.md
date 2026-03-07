# Runtime Event Stream And TUI Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Introduce a first-class runtime event stream so TeamBot can drive a Claude Code style TUI with step-by-step `Thinking / Tool / Result / Final` updates while keeping the current `OutboundReply` interface.

**Architecture:** Add a unified `RuntimeEvent` model in `domain`, then emit those events from the agent loop instead of forcing presentation layers to reconstruct state from `reasoning_note`, provider callbacks, and `execution_trace`. `AgentService` will expose a streaming interface for UI clients while preserving `process_event(...) -> OutboundReply` for API and compatibility. The future TUI will subscribe to runtime events and render a per-step transcript instead of a post-hoc summary.

**Tech Stack:** Python, Pydantic, pytest, TeamBot agent runtime, Textual-ready event stream foundation.

---

### Task 1: Define Runtime Event Contracts

**Files:**
- Modify: `src/teambot/domain/models.py`
- Test: `tests/test_runtime_events.py`

**Step 1: Write the failing test**

Add tests that define:
- a `RuntimeEvent` model with stable fields like `run_id`, `step`, `event_type`, `text`, `action_name`, `action_input`, `observation`
- allowed event types for at least `task_started`, `thinking`, `tool_call`, `tool_result`, `final_text`, `run_completed`
- an `OutboundReply` that can keep existing fields unchanged

**Step 2: Run test to verify it fails**

Run: `pytest -q tests/test_runtime_events.py`

Expected: FAIL because `RuntimeEvent` does not exist yet.

**Step 3: Write minimal implementation**

Implement the `RuntimeEvent` model and minimal helper typing in `src/teambot/domain/models.py`.

**Step 4: Run test to verify it passes**

Run: `pytest -q tests/test_runtime_events.py`

Expected: PASS

### Task 2: Add Runtime Event Sink To Agent Loop

**Files:**
- Modify: `src/teambot/agent/runtime.py`
- Modify: `src/teambot/agent/graph.py`
- Modify: `src/teambot/agent/reason.py`
- Modify: `src/teambot/agent/execution.py`
- Test: `tests/test_runtime_events.py`

**Step 1: Write the failing test**

Add tests that build a tiny runtime with stub action registry / stub reasoner and assert events are emitted in order, for example:
- `task_started`
- `thinking`
- `tool_call`
- `tool_result`
- `thinking`
- `final_text`
- `run_completed`

**Step 2: Run test to verify it fails**

Run: `pytest -q tests/test_runtime_events.py -k emit`

Expected: FAIL because runtime does not emit events.

**Step 3: Write minimal implementation**

Add a runtime event callback/sink that is threaded through:
- `TeamBotRuntime`
- `AgentCoreRuntime`
- `reason.py`
- `execution.py`

Emit only the minimum stable events first.

**Step 4: Run test to verify it passes**

Run: `pytest -q tests/test_runtime_events.py -k emit`

Expected: PASS

### Task 3: Expose `stream_event(...)` From AgentService

**Files:**
- Modify: `src/teambot/agent/service.py`
- Modify: `src/teambot/domain/models.py`
- Test: `tests/test_runtime_events.py`

**Step 1: Write the failing test**

Add tests for a new service interface that yields runtime events and a final `OutboundReply`, while preserving idempotency behavior.

**Step 2: Run test to verify it fails**

Run: `pytest -q tests/test_runtime_events.py -k service`

Expected: FAIL because no streaming interface exists.

**Step 3: Write minimal implementation**

Implement a streaming service method, likely `stream_event(...)`, that:
- checks processed-event cache
- builds initial state
- collects runtime events
- yields them in order
- returns or exposes the final `OutboundReply`

Keep `process_event(...)` working by consuming the same core path.

**Step 4: Run test to verify it passes**

Run: `pytest -q tests/test_runtime_events.py -k service`

Expected: PASS

### Task 4: Rebase CLI Onto Runtime Events

**Files:**
- Modify: `src/teambot/app/cli.py`
- Test: `tests/test_cli_modes.py`

**Step 1: Write the failing test**

Add tests that assert the CLI transcript is driven by ordered runtime events instead of ad-hoc mixing of:
- `reasoning_note`
- provider callbacks
- `execution_trace`

**Step 2: Run test to verify it fails**

Run: `pytest -q tests/test_cli_modes.py`

Expected: FAIL because CLI still builds transcript from legacy fields.

**Step 3: Write minimal implementation**

Refactor CLI rendering to consume runtime events first, while keeping current slash commands and `OutboundReply` fallback behavior.

**Step 4: Run test to verify it passes**

Run: `pytest -q tests/test_cli_modes.py`

Expected: PASS

### Task 5: Add TUI Entry Point

**Files:**
- Create: `src/teambot/app/tui.py`
- Modify: `pyproject.toml`
- Test: `tests/test_tui_smoke.py`

**Step 1: Write the failing test**

Add a smoke test that verifies:
- the TUI module imports
- it can build a transcript controller around the streaming service interface

**Step 2: Run test to verify it fails**

Run: `pytest -q tests/test_tui_smoke.py`

Expected: FAIL because `tui.py` does not exist yet.

**Step 3: Write minimal implementation**

Create the first TUI shell with:
- top status/header
- transcript timeline
- bottom input box
- slash command passthrough

Do not overbuild inspector panels in the first pass.

**Step 4: Run test to verify it passes**

Run: `pytest -q tests/test_tui_smoke.py`

Expected: PASS

### Task 6: Update Canonical Docs

**Files:**
- Modify: `docs/README.md`
- Modify: `docs/code-structure.md`
- Modify: `docs/agent-core-algorithm.md`
- Modify: `repo_wiki.md`

**Step 1: Update docs after implementation**

Document:
- the runtime event model
- the service streaming interface
- CLI/TUI responsibility split
- how the agent transcript is now emitted

**Step 2: Run final verification**

Run: `pytest -q`

Expected: PASS

**Step 3: Commit**

```bash
git add docs/plans/2026-03-07-runtime-event-stream-and-tui.md src/teambot tests docs repo_wiki.md pyproject.toml
git commit -m "feat: add runtime event stream foundation for tui"
```
