# Skill Activation Context Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remove executable Python skill plugins and replace them with a context-loading `activate_skill` tool that expands selected `SKILL.md` files into the reasoner context.

**Architecture:** Runtime actions will be limited to tools and deterministic event handlers. Skill docs will stay under `src/teambot/skills/` as catalog and context data only; the model will see skill metadata in the reasoner request and can call `activate_skill` to load a skill doc into state for the next reasoning step.

**Tech Stack:** Python, FastAPI, Pydantic, pytest

---

### Task 1: Lock the new runtime contract with tests

**Files:**
- Modify: `tests/test_reasoner_skill_context.py`
- Modify: `tests/test_external_operation_tools.py`
- Modify: `tests/test_runtime_orchestrator.py`
- Modify: `tests/test_react_agent.py`
- Modify: `tests/test_core_structure.py`

**Step 1: Write failing tests**

- Assert `activate_skill` is exposed as a tool even under the minimal tool profile.
- Assert calling `activate_skill` loads the selected skill doc into state and the next reasoner request includes the expanded active skill doc.
- Assert runtime/orchestrator no longer expose a skill registry.
- Assert code structure no longer requires dynamic skill plugin files under `src/teambot/skills/`.

**Step 2: Run targeted tests to verify they fail**

Run:

```bash
PYTHONPATH=src python -m pytest tests/test_reasoner_skill_context.py tests/test_external_operation_tools.py tests/test_runtime_orchestrator.py tests/test_react_agent.py tests/test_core_structure.py -q
```

Expected:
- Failing assertions around missing `activate_skill`
- Failing references to removed runtime skill registry semantics

### Task 2: Implement skill activation and remove executable skill plugins

**Files:**
- Modify: `src/teambot/domain/models.py`
- Modify: `src/teambot/agent/state.py`
- Modify: `src/teambot/agent/graph.py`
- Modify: `src/teambot/agent/runtime.py`
- Modify: `src/teambot/agent/orchestrator.py`
- Modify: `src/teambot/actions/registry.py`
- Modify: `src/teambot/actions/tools/catalog.py`
- Modify: `src/teambot/actions/tools/external_operation_tools.py`
- Modify: `src/teambot/actions/tools/profiles.py`
- Modify: `src/teambot/actions/tools/runtime_builder.py`
- Modify: `src/teambot/skills/manager.py`
- Modify: `src/teambot/skills/context.py`
- Modify: `src/teambot/skills/__init__.py`
- Delete: `src/teambot/skills/registry.py`
- Delete: `src/teambot/skills/dynamic.py`
- Delete: `src/teambot/skills/runtime_loader.py`
- Delete: `src/teambot/skills/builtin.py`

**Step 1: Add state fields for active skill context**

- Add `active_skill_names` and `active_skill_docs` to `AgentState`.
- Initialize them in `build_initial_state`.

**Step 2: Add a minimal skill catalog lookup API**

- Extend `SkillDoc` metadata parsing to include `when_to_use`.
- Add a lookup helper on `SkillService` for `get_skill_doc(name)`.

**Step 3: Add the `activate_skill` tool**

- Register a low-risk tool named `activate_skill`.
- Its handler should:
  - read `skill_name` from `action_input`
  - resolve the skill from the catalog
  - write the selected doc into state via a structured state update
  - return a short confirmation message

**Step 4: Let action execution apply tool-driven state updates**

- Update the action execution path so a tool can return a structured state update without leaking the full skill body into the visible observation text.

**Step 5: Remove runtime skill registry wiring**

- Remove `SkillRegistry` from runtime, graph, orchestrator, and plugin host.
- Keep action sources limited to `tool` and `event_handler`.

### Task 3: Rework reasoner skill context assembly

**Files:**
- Modify: `src/teambot/skills/context.py`
- Modify: `src/teambot/agent/reasoner_context.py`
- Modify: `src/teambot/agent/reason.py`

**Step 1: Split catalog metadata from active skill docs**

- Always expose bounded skill catalog metadata (`name`, `description`, `when_to_use`) to the reasoner.
- Only inject full/expanded skill docs from `state["active_skill_docs"]`.

**Step 2: Keep the tool schema clean**

- Ensure only actual tools appear in the reasoner tool schema.
- `activate_skill` is a tool; skill docs themselves are not executable actions.

### Task 4: Update docs and verification

**Files:**
- Modify: `docs/agent-core-algorithm.md`
- Modify: `docs/code-structure.md`
- Modify: `docs/README.md`
- Modify: `docs/modules/getting-started.md`
- Modify: `repo_wiki.md`

**Step 1: Update runtime semantics docs**

- Remove references to dynamic skill plugins.
- Document the new `activate_skill` flow and active skill context state.

**Step 2: Run targeted verification**

Run:

```bash
PYTHONPATH=src python -m pytest tests/test_reasoner_skill_context.py tests/test_external_operation_tools.py tests/test_runtime_orchestrator.py tests/test_react_agent.py tests/test_core_structure.py -q
```

Then run a broader regression slice:

```bash
PYTHONPATH=src python -m pytest tests/test_reason_planner.py tests/test_action_policy.py tests/test_runtime_events.py tests/test_memory_context.py tests/test_interface_parity.py -q
```
