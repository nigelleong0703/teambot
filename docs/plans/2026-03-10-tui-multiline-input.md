# TUI Multiline Input Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the TUI's single-line `input()` loop with a multiline-capable terminal input layer that handles long pasted text safely.

**Architecture:** Keep the existing transcript renderer and runtime event loop unchanged. Introduce a small TUI input adapter that prefers `prompt_toolkit` for multiline editing and falls back to the current plain input path if the dependency is unavailable or stdin is not interactive.

**Tech Stack:** Python 3.11, `prompt_toolkit`, pytest

---

### Task 1: Add failing tests for multiline input plumbing

**Files:**
- Modify: `tests/test_tui_smoke.py`
- Test: `tests/test_tui_smoke.py`

**Step 1: Write the failing tests**

Add tests that assert:
- `TeamBotTuiApp` can use an injected input reader instead of raw `input()`
- multiline input is preserved and forwarded into the built `InboundEvent.text`
- the fallback reader still trims surrounding whitespace and returns plain text

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_tui_smoke.py`

Expected: FAIL because `TeamBotTuiApp` does not yet support an input-reader abstraction.

**Step 3: Write minimal implementation**

Create a small input adapter boundary in the TUI app constructor and run loop.

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_tui_smoke.py`

Expected: PASS for the new tests.

**Step 5: Commit**

```bash
git add tests/test_tui_smoke.py src/teambot/app/tui.py
git commit -m "feat: add tui input reader abstraction"
```

### Task 2: Add a prompt-toolkit input session with fallback

**Files:**
- Create: `src/teambot/app/tui_input.py`
- Modify: `src/teambot/app/tui.py`
- Modify: `requirements.txt`
- Modify: `requirements-dev.txt`
- Test: `tests/test_tui_smoke.py`

**Step 1: Write the failing test**

Add tests that assert:
- the default input factory returns a prompt-toolkit-backed reader when the library is available
- the fallback path returns a plain single-line reader when the library import fails

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_tui_smoke.py`

Expected: FAIL because the input session module does not yet exist.

**Step 3: Write minimal implementation**

Implement:
- a plain reader wrapper over built-in `input()`
- a prompt-toolkit reader with multiline editing
- stable key handling:
  - `Enter` submits
  - `Escape` then `Enter` inserts newline
  - continuation prompt for wrapped lines

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_tui_smoke.py`

Expected: PASS for input-session tests.

**Step 5: Commit**

```bash
git add src/teambot/app/tui_input.py src/teambot/app/tui.py requirements.txt requirements-dev.txt tests/test_tui_smoke.py
git commit -m "feat: add multiline tui input session"
```

### Task 3: Update TUI usage docs

**Files:**
- Modify: `docs/modules/getting-started.md`
- Modify: `repo_wiki.md`

**Step 1: Write the doc update**

Document:
- TUI now supports multiline composition
- default submit/newline keys
- fallback behavior when `prompt_toolkit` is unavailable

**Step 2: Verify docs are accurate against code**

Run:

```bash
rg -n "multiline|Escape|prompt_toolkit|fallback" src/teambot/app/tui.py src/teambot/app/tui_input.py docs/modules/getting-started.md repo_wiki.md
```

Expected: matching wording and no stale keybinding references.

**Step 3: Commit**

```bash
git add docs/modules/getting-started.md repo_wiki.md
git commit -m "docs: document tui multiline input"
```

### Task 4: Verify the focused change

**Files:**
- Test: `tests/test_tui_smoke.py`

**Step 1: Install/update dependencies**

Run:

```bash
.venv/bin/python -m pip install -r requirements-dev.txt
```

**Step 2: Run focused verification**

Run:

```bash
PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_tui_smoke.py
```

Expected: PASS

**Step 3: Run a second regression slice**

Run:

```bash
PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_cli_modes.py tests/test_runtime_events.py
```

Expected: PASS, proving the TUI input change did not break transcript rendering or runtime event handling.

**Step 4: Commit**

```bash
git add requirements.txt requirements-dev.txt src/teambot/app/tui.py src/teambot/app/tui_input.py tests/test_tui_smoke.py docs/modules/getting-started.md repo_wiki.md
git commit -m "feat: support multiline tui input"
```
