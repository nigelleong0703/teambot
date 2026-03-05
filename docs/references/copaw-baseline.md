# CoPaw Baseline (for gradual parity)

## 1) What CoPaw is

CoPaw is a ReAct agent runtime built on top of AgentScope + AgentScope Runtime.
It is not just a skill registry. It combines:

- Open tool calls (`read`, `edit`, `exec`, browser, etc.)
- Skill directories (`SKILL.md`, optional `scripts/`, `references/`)
- Working-directory-driven behavior (`~/.copaw`)
- Channel connectors + cron + MCP + memory compaction

Core references:

- `src/copaw/agents/react_agent.py`
- `src/copaw/app/_app.py`
- `src/copaw/app/runner/runner.py`
- `src/copaw/agents/skills_manager.py`

## 2) Runtime chain (high level)

1. CLI entry: `python -m copaw` -> `src/copaw/cli/main.py`
2. App startup: `src/copaw/app/_app.py` creates FastAPI app + runner
3. Runner query handling: `src/copaw/app/runner/runner.py`
4. Agent instance per query: `CoPawAgent` from `src/copaw/agents/react_agent.py`
5. ReAct loop executes with toolkit + skills + memory + MCP

## 3) Tools: what is actually active in CoPaw

`react_agent.py` registers this built-in subset into toolkit at runtime:

- `execute_shell_command`
- `read_file`
- `write_file`
- `edit_file`
- `browser_use`
- `desktop_screenshot`
- `send_file_to_user`
- `get_current_time`

Reference: `src/copaw/agents/react_agent.py` (`_create_toolkit`).

Notes:

- `src/copaw/agents/tools/__init__.py` exports a larger set (e.g. `append_file`, `grep_search`, `glob_search`), but not all are auto-registered in `_create_toolkit`.
- `memory_search` is conditionally added only when memory manager is enabled.

## 4) Skills mechanism in CoPaw

### 4.1 Skill shape

A skill is a directory with:

- `SKILL.md` (required)
- `scripts/` (optional)
- `references/` (optional)

Example locations:

- `src/copaw/agents/skills/file_reader/SKILL.md`
- `src/copaw/agents/skills/pdf/scripts/...`

### 4.2 Active skill set

CoPaw has three skill locations:

- builtin skills: code repo (`src/copaw/agents/skills`)
- customized skills: `~/.copaw/customized_skills`
- active skills: `~/.copaw/active_skills` (what agent actually uses)

At runtime, only `active_skills` are registered.
Reference:

- `list_available_skills()` in `src/copaw/agents/skills_manager.py`
- `_register_skills()` in `src/copaw/agents/react_agent.py`

### 4.3 Enable/disable flow

Skill activation is managed by CLI:

- `copaw skills list`
- `copaw skills config` (interactive enable/disable)

Reference: `src/copaw/cli/skills_cmd.py`.

## 5) Prompt + behavior injection model

CoPaw system prompt is built from working-dir markdown files:

- `AGENTS.md` (required)
- `SOUL.md` (required)
- `PROFILE.md` (optional)

Reference: `src/copaw/agents/prompt.py`.

This is a key reason CoPaw feels "open": behavior is heavily shaped by runtime docs + skill docs, not only Python handler code.

## 6) Security posture implied by CoPaw

CoPaw init flow explicitly warns:

- tool-enabled agents are risky
- use stronger models for tool use / untrusted input
- restrict channels/users and apply least privilege

Reference: `src/copaw/cli/init_cmd.py` (`SECURITY_WARNING`).

## 7) Where current TeamBot differs

Current TeamBot already has:

- ReAct-like graph loop
- dynamic Python plugin loading (`SKILLS_DIR`)
- model planner fallback

But differs from CoPaw in these important ways:

1. Skills are function plugins, not CoPaw-style `SKILL.md + scripts + references` packages.
2. No `active/customized/builtin` skill lifecycle yet.
3. No CLI skill enable/disable UX yet.
4. Open tool subset policy is not yet first-class and centrally managed.
5. Prompt assembly from working-dir docs is still lightweight.

## 8) Practical parity plan (incremental)

Phase A (foundation parity):

1. Introduce `builtin_skills/`, `customized_skills/`, `active_skills/`.
2. Implement skill sync and activation API (CoPaw-like manager).
3. Parse `SKILL.md` metadata and inject selected skill docs into planner context.

Phase B (open tool parity):

1. Add first-class tool registry with explicit runtime subset.
2. Start with subset: `read_file`, `edit_file`, `execute_shell_command`, `get_current_time`.
3. Add hard policy gates for `exec` and write operations.

Phase C (ops parity):

1. Add skill list/config CLI.
2. Add stronger prompt assembly from working-dir docs.
3. Add memory/MCP/channel integrations as needed.

## 9) Scope recommendation for next implementation step

Do not clone all CoPaw modules at once.
Implement "CoPaw-compatible skill lifecycle + tool subset gate" first.
This gives immediate parity on the parts that matter most for your architecture decision.
