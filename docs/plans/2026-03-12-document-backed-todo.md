# Document-Backed Todo Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the old `/todo` command-style behavior with a Claude Code-style TodoWrite flow backed by `todo.md` in the agent work directory.

**Architecture:** Todo state is represented in code as structured objects, persisted as a canonical human-readable Markdown document, and exposed through dedicated `todo_read` and `todo_write` tools. The runtime no longer treats `/todo` as a deterministic command and does not use reactions to mutate todo state.

**Tech Stack:** Python, Pydantic/dataclasses, Markdown parsing/rendering, pytest

---

### Task 1: Remove the old `/todo` deterministic route

**Files:**
- Modify: `src/teambot/agent/reason.py`
- Modify: `src/teambot/actions/event_handlers/builtin.py`
- Test: `tests/test_skills.py`
- Test: `tests/test_interface_parity.py`
- Test: `tests/test_reasoner_skill_context.py`

**Step 1: Write the failing tests**

- Update tests that currently expect `/todo` to route to `create_task`.
- Add assertions that `/todo write docs` no longer selects `create_task`.
- Keep reaction event coverage only if reaction handling remains intentionally supported outside todo flow.

**Step 2: Run the targeted tests to verify they fail**

Run: `uv run --with-requirements requirements-dev.txt pytest tests/test_skills.py tests/test_interface_parity.py tests/test_reasoner_skill_context.py -q`

Expected: failures that prove the old `/todo` route assumptions are no longer correct.

**Step 3: Write the minimal implementation**

- Remove the `/todo` branch from `_deterministic_direct_route`.
- Remove `create_task` from the built-in event handler registry.
- Adjust any tests or runtime assumptions that still expose `create_task` as an event handler action.

**Step 4: Re-run the targeted tests**

Run: `uv run --with-requirements requirements-dev.txt pytest tests/test_skills.py tests/test_interface_parity.py tests/test_reasoner_skill_context.py -q`

Expected: passing tests for the removed route and updated action surface.

### Task 2: Add todo domain and Markdown codec

**Files:**
- Create: `src/teambot/todo/models.py`
- Create: `src/teambot/todo/codec.py`
- Create: `src/teambot/todo/__init__.py`
- Test: `tests/test_todo_document.py`

**Step 1: Write the failing tests**

- Add tests for parsing `todo.md` Markdown into structured todo items.
- Add tests for rendering structured todo items back into canonical Markdown.
- Add tests for empty todo lists and normalized numbering/status formatting.

**Step 2: Run the targeted tests to verify they fail**

Run: `uv run --with-requirements requirements-dev.txt pytest tests/test_todo_document.py -q`

Expected: failures due to missing todo model/codec modules.

**Step 3: Write the minimal implementation**

- Define `TodoStatus`, `TodoItem`, and `TodoList`.
- Implement Markdown parsing for this canonical format:

```md
# Tasks

## 1. Task title
- **Active Form**: Doing the task
- **Status**: Pending
```

- Implement canonical rendering that rewrites the full document in a stable format.

**Step 4: Re-run the targeted tests**

Run: `uv run --with-requirements requirements-dev.txt pytest tests/test_todo_document.py -q`

Expected: all todo document tests pass.

### Task 3: Add repository and TodoWrite-style service

**Files:**
- Create: `src/teambot/todo/repository.py`
- Create: `src/teambot/todo/service.py`
- Modify: `src/teambot/runtime_paths.py`
- Test: `tests/test_todo_service.py`

**Step 1: Write the failing tests**

- Add tests for default `todo.md` location under the agent work directory.
- Add tests for loading an empty/nonexistent todo file.
- Add tests for `todo_write` replacing the full list and returning `old_todos/new_todos`.
- Add tests for clearing persisted items when every todo is completed.

**Step 2: Run the targeted tests to verify they fail**

Run: `uv run --with-requirements requirements-dev.txt pytest tests/test_todo_service.py -q`

Expected: failures because repository/service code does not exist yet.

**Step 3: Write the minimal implementation**

- Add `get_agent_todo_path()` returning `<agent_home>/work/todo.md`.
- Implement repository load/save with atomic file writes.
- Implement service methods for `read()` and `write()` using full-list replacement semantics.

**Step 4: Re-run the targeted tests**

Run: `uv run --with-requirements requirements-dev.txt pytest tests/test_todo_service.py -q`

Expected: all todo service tests pass.

### Task 4: Expose todo tools in the runtime tool registry

**Files:**
- Modify: `src/teambot/actions/tools/catalog.py`
- Modify: `src/teambot/actions/tools/profiles.py`
- Modify: `src/teambot/actions/tools/runtime_builder.py`
- Modify: `src/teambot/actions/tools/external_operation_tools.py`
- Test: `tests/test_external_operation_tools.py`
- Test: `tests/test_plugin_host.py`

**Step 1: Write the failing tests**

- Add tests that `todo_read` and `todo_write` are present in the external-operation/full tool profiles.
- Add tests that `todo_write` persists Markdown to `todo.md`.
- Add tests that `todo_read` returns parsed structured items from `todo.md`.

**Step 2: Run the targeted tests to verify they fail**

Run: `uv run --with-requirements requirements-dev.txt pytest tests/test_external_operation_tools.py tests/test_plugin_host.py -q`

Expected: failures due to missing manifests/handlers.

**Step 3: Write the minimal implementation**

- Add low-risk tool manifests for `todo_read` and `todo_write`.
- Implement handlers that resolve the runtime working directory, then use the todo repository/service layer.
- Ensure tool outputs are normalized and user-facing.

**Step 4: Re-run the targeted tests**

Run: `uv run --with-requirements requirements-dev.txt pytest tests/test_external_operation_tools.py tests/test_plugin_host.py -q`

Expected: passing tool and registry tests.

### Task 5: Update algorithm and runtime documentation

**Files:**
- Modify: `docs/agent-core-algorithm.md`
- Modify: `docs/README.md`
- Modify: `docs/code-structure.md`
- Modify: `repo_wiki.md`

**Step 1: Update canonical behavior docs**

- Remove references that position `/todo` as a deterministic event route.
- Document `todo_read`/`todo_write` as document-backed runtime tools.
- State that `todo.md` lives in the agent work directory and is the persisted todo source of truth.

**Step 2: Review doc consistency**

Run: `rg -n "/todo|create_task|TodoWrite|todo.md" docs repo_wiki.md src tests`

Expected: only intended current-state references remain.

### Task 6: Final verification

**Files:**
- Verify only

**Step 1: Run focused verification**

Run: `uv run --with-requirements requirements-dev.txt pytest tests/test_todo_document.py tests/test_todo_service.py tests/test_external_operation_tools.py tests/test_plugin_host.py tests/test_skills.py tests/test_interface_parity.py tests/test_reasoner_skill_context.py -q`

Expected: all targeted tests pass.

**Step 2: Run a repo-wide todo surface check**

Run: `rg -n "/todo|create_task|todo_read|todo_write|todo.md" src tests docs repo_wiki.md`

Expected: matches the new design and no stale `/todo -> create_task` behavior remains in current-state docs/code.
