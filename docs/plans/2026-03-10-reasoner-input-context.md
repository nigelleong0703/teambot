# Reasoner Input Context Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Introduce a dedicated assembler for reasoner input context so prompt and payload assembly no longer scatter memory and skill context logic across `reason.py`.

**Architecture:** Keep memory context and skill context as separate bounded providers, then compose them through a new reasoner request context layer. This keeps `memory/` responsible for transcript and long-term memory, `skills/` responsible for skill docs, and `agent/` responsible for the final reasoner request contract.

**Tech Stack:** Python, pytest

---

### Task 1: Add failing tests for unified reasoner context assembly

**Files:**
- Modify: `tests/test_reasoner_skill_context.py`
- Test: `tests/test_reasoner_skill_context.py`

**Step 1: Write the failing test**

Add tests asserting that a dedicated assembler:
- includes runtime working dir in the reasoner payload;
- combines skill docs and memory suffix once;
- returns prompt/payload sections that `reason.py` can consume without reassembling them ad hoc.

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_reasoner_skill_context.py -q`
Expected: FAIL because the dedicated assembler does not exist yet and payload does not include runtime context.

### Task 2: Implement the assembler and rewire reasoner input construction

**Files:**
- Create: `src/teambot/agent/reasoner_context.py`
- Modify: `src/teambot/agent/reason.py`

**Step 1: Write minimal implementation**

Create a small dataclass-based assembler that:
- reads state memory fields;
- reads bounded skill context;
- exposes `system_prompt_suffix` and payload additions;
- includes `runtime_working_dir` in payload when present.

**Step 2: Run targeted tests**

Run: `pytest tests/test_reasoner_skill_context.py -q`
Expected: PASS.

### Task 3: Verify broader runtime compatibility

**Files:**
- Test: `tests/test_memory_context.py`
- Test: `tests/test_interface_parity.py`

**Step 1: Run compatibility checks**

Run: `pytest tests/test_memory_context.py tests/test_interface_parity.py tests/test_reasoner_skill_context.py -q`
Expected: PASS.
