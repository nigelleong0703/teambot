## Context

TeamBot currently exposes a unified runtime action surface where both built-in skills (`create_task`, `handle_reaction`) and external-operation tools are executed through the same action contract. This worked for early bootstrapping, but it creates semantic ambiguity:
- users and contributors read "skill" as knowledge/context, while runtime treats it as executable action;
- event-driven deterministic behavior and model-selected tool-calling are mixed;
- planner naming implies long-horizon planning while actual behavior is per-step reasoning selection.

The change must preserve existing runtime stability (`reason -> act -> observe -> compose_reply`) while clarifying behavior and terminology.

## Goals / Non-Goals

**Goals:**
- Make executable model-callable surface strictly tool-based.
- Treat skills as reasoning context resources (docs) rather than executable runtime actions.
- Move deterministic event/command logic into explicit event handlers.
- Add CLI parity for skills lifecycle operations.
- Rename runtime-facing terms toward reasoning/action semantics with backward-compatible migration.

**Non-Goals:**
- Replacing provider integrations or model adapters.
- Introducing new tool categories beyond current external-operation baseline.
- Removing HTTP skills lifecycle APIs.
- Reworking the core loop structure itself.

## Decisions

### 1) Introduce explicit runtime role split: `tool`, `event_handler`, `skill_context`

Decision:
- Keep one runtime selection envelope (`action`) for execution outputs/tracing.
- Restrict model tool-calling candidates to `tool` source only.
- Keep deterministic event handlers outside model tool-call surface.
- Use skill docs only in reasoning context assembly.

Rationale:
- Preserves existing execution ergonomics while removing semantic overload.
- Prevents model from invoking deterministic business handlers as if they were generic tools.

Alternatives considered:
- Keep current mixed registry and document it better.
  - Rejected: terminology confusion remains and model-call surface stays broader than intended.
- Split into entirely separate execution engines.
  - Rejected: unnecessary complexity for current runtime scope.

### 2) Add reasoning context assembler for skill docs injection

Decision:
- Build a dedicated assembler that reads active skill docs and emits:
  - compact skill index summary for system prompt extension;
  - bounded detail payload attached to planner/reasoner request payload.
- Enforce deterministic truncation limits.

Rationale:
- Gives model awareness of active skills without making skills executable.
- Avoids prompt bloat and preserves token budget predictability.

Alternatives considered:
- Inject full `SKILL.md` content directly into system prompt.
  - Rejected: high token risk and weaker control.
- Expose a runtime tool to fetch skill docs on demand only.
  - Deferred: useful extension, but not required for baseline separation.

### 3) Rename planner-facing semantics with compatibility layer

Decision:
- Introduce `reasoner` naming in runtime modules and docs.
- State contract migrates from `selected_skill/skill_input/skill_output` to `selected_action/action_input/action_output`.
- Keep compatibility aliases during rollout to avoid immediate breakage in tests/integrations.

Rationale:
- Names match actual behavior and reduce onboarding confusion.

Alternatives considered:
- Hard rename in one pass.
  - Rejected: higher regression risk.

### 4) CLI skills lifecycle parity

Decision:
- Add interactive CLI commands:
  - `/skills`
  - `/skills sync`
  - `/skills enable <name>`
  - `/skills disable <name>`
- Reuse existing `SkillService` behavior and trigger runtime reload after mutations.

Rationale:
- Aligns CLI operator workflow with existing HTTP APIs.

## Risks / Trade-offs

- [Risk] Compatibility drift between old and new state keys in transition  
  -> Mitigation: dual-write + dual-read helper utilities and targeted tests.

- [Risk] Skill-doc injection could increase latency/token usage  
  -> Mitigation: bounded excerpt budget, deterministic truncation, debug visibility.

- [Risk] Event handler extraction can change routing precedence unexpectedly  
  -> Mitigation: explicit precedence tests for reaction, `/todo`, and planner fallback flows.

- [Risk] CLI command ambiguity with existing slash command handling  
  -> Mitigation: reserve command parsing table and add help output coverage tests.

## Migration Plan

1. Introduce compatibility shims for action-vs-skill state fields.
2. Move deterministic handlers (`create_task`, `handle_reaction`) to event handler path.
3. Restrict planner/reasoner tool specs to tool-only registry.
4. Add skill context assembler and wire to prompt/payload build path.
5. Add CLI skills commands and runtime reload behavior.
6. Update docs and tests; remove obsolete naming usage where safe.

Rollback:
- Re-enable previous mixed action registration behind a temporary compatibility toggle if regressions are detected.
- Keep prior state fields available for one release cycle so rollback does not require data/state migration.

## Open Questions

- Should a read-only `get_skill_doc` tool be introduced in the same change, or deferred?
- How much skill-doc detail should be included by default in payload vs system prompt for best model quality/cost?
