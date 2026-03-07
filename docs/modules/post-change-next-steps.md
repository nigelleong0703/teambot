# Post-Change Next Steps

## Goal

After the native tool-calling refactor is merged, execute the next phase in a clean and repeatable order.

## CoPaw Gap Status (as of 2026-03-05)

This section updates the earlier "not aligned yet" assessment based on current code.

1. Open tools parity (`read/edit/write/exec/browser/time`)
   - Status: **Done (baseline subset landed)**
   - Notes:
     - Runtime tool profiles are active.
     - Native model tool-calling is enabled with tool schemas.
2. Skill docs injected into model decision
   - Status: **Todo**
   - Notes:
     - `SkillService.list_available_skill_docs()` exists, but is not injected into planner payload/prompt.
3. CLI skills UX (`skills list/config`)
   - Status: **Partial**
   - Notes:
     - HTTP skills APIs exist (`/skills`, `/skills/sync`, enable/disable).
     - CLI interactive skills management commands are still missing.
4. Prompt constraints strength vs CoPaw
   - Status: **Todo**
   - Notes:
     - Missing `AGENTS.md` still falls back to default prompt.
     - CoPaw-style stricter required docs behavior is not enforced.
5. Security policy granularity
   - Status: **Partial**
   - Notes:
     - High-risk gate + allowlist exists.
     - Missing path sandbox/command budget/timeout governance policy layer.
6. MCP / channels / cron / memory compaction
   - Status: **Partial**
   - Notes:
     - MCP bridge/runtime injection exists.
     - channels/cron/memory compaction are not implemented yet.
7. Router capability ("default deterministic only")
   - Status: **Done (obsolete old finding)**
   - Notes:
     - Router now supports native model tool calls and final text fallback.

## Next Step Backlog (priority order)

1. Inject active skill docs into planner context
   - Wire `list_available_skill_docs()` into router/provider payload build.
   - Add tests to verify skill-doc-aware routing behavior.
2. Add CLI skills management parity
   - Add `/skills`, `/skills sync`, `/skills enable <name>`, `/skills disable <name>`.
   - Keep behavior consistent with existing HTTP skills API.
3. Harden execution policy
   - Add file path policy (allow/deny boundaries).
   - Add command policy (allow/deny rules, budgets).
   - Add per-tool timeout/output limits in policy layer (not only handler defaults).
4. Strengthen working-dir prompt contract
   - Add strict mode that requires `AGENTS.md` (and optionally `SOUL.md`) for agent_model calls.
5. Expand platform capabilities
   - Add channel adapters, cron scheduling, memory compaction as separate modules.

## Step 1: Runtime Sanity (local)

1. Run tests:
   - `pytest -q`
2. Run CLI in external-operation profile:
   - `python -m teambot.app.cli --tools-profile external_operation --show-model-payload`
3. In CLI, verify:
   - `/tools` shows expected runtime tools.
   - `check my current time` triggers `get_current_time`.
   - debug payload includes `[debug] tools:` schema list.

## Step 2: Provider and Env Hardening

1. Confirm provider env keys are valid in local `.env`.
2. Keep `.env.template` aligned with all runtime env keys.
3. Run provider smoke test:
   - `python -m teambot.app.provider_smoke_test --pretty`

## Step 3: Tool Governance (granular control)

1. Finalize JSON/YAML-based tool toggles per tool (on/off).
2. Keep `tools-profile` as preset wrapper on top of per-tool overrides.
3. Ensure CLI help clearly explains both:
   - profile selection
   - per-tool override behavior

## Step 4: Agent-First Structure (tools + skills + mcp)

1. Keep runtime flow centered in `agent/runtime.py` and `agent/*`.
2. Treat `tools`, `skills`, `mcp` as first-class parallel capability modules.
3. Preserve single action surface through plugin host/action registry.

## Step 5: Observability and Debug UX

1. Keep model payload debug mode stable (`system_prompt`, `request_payload`, `tools`).
2. Keep action trace readable from `execution_trace`.
3. Add targeted tests whenever routing or tool-call behavior changes.

## Step 6: Branch and Release Discipline

1. Create a `codex/*` branch for each feature-sized change.
2. Keep commit scope tight (no mixed unrelated refactor + feature).
3. Merge to `main` only after:
   - tests pass
   - docs updated
   - runtime behavior verified in CLI

## Definition of Done (for each future change)

- Tests: pass
- CLI: verified with real tool call
- Docs: updated (`docs/*` + `repo_wiki.md` when runtime flow changed)
- Branch hygiene: merged and cleaned up
