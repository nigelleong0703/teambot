## Context

TeamBot currently exposes `message_reply` as the only practical built-in tool, while `tool_echo` and `exec_command` are optional placeholders. In contrast, CoPaw's runtime registers a concrete open-tools subset (`read_file`, `write_file`, `edit_file`, `execute_shell_command`, `browser_use`, `get_current_time`, plus optional `desktop_screenshot` and `send_file_to_user`).

The gap is now the largest functional mismatch between TeamBot and CoPaw baseline behavior. TeamBot already has a unified action runtime and policy gate contract, so the missing part is concrete tool implementations and deterministic registry wiring.

Constraints:
- Keep current `reason -> act -> observe -> compose_reply` runtime shape unchanged.
- Preserve backward compatibility for `message_reply` as safe default.
- Keep risky operations policy-gated and disabled by default unless explicitly allowed.
- Keep env-key ownership in `.env.template` aligned with runtime behavior.

## Goals / Non-Goals

**Goals:**
- Introduce CoPaw-aligned built-in open-tools in TeamBot with deterministic registration.
- Replace placeholders with executable handlers and consistent output envelopes.
- Keep high-risk operations (`execute_shell_command`, `write_file`, `edit_file`) centrally policy-gated.
- Provide staged rollout via explicit environment toggles and sensible defaults.
- Add tests and docs that pin the new behavior and prevent drift.

**Non-Goals:**
- Full CoPaw runtime clone (memory manager, channels, cron, MCP lifecycle).
- Migrating TeamBot skill packaging to CoPaw `SKILL.md` lifecycle in this change.
- Adding every tool exported by CoPaw `tools/__init__.py`.
- Changing planner architecture or step-loop semantics.

## Decisions

1. **Define a canonical TeamBot built-in open-tools subset**
   - Decision: Register `read_file`, `write_file`, `edit_file`, `execute_shell_command`, `browser_use`, and `get_current_time` as first-class built-in tool actions.
   - Optional extensions (`desktop_screenshot`, `send_file_to_user`) are feature-flagged and disabled by default.
   - Rationale: matches the practical CoPaw baseline while keeping scope controlled.
   - Alternative considered: register all CoPaw-exported tools immediately; rejected due to higher regression surface and policy complexity.

2. **Keep one normalized action output envelope**
   - Decision: All built-in tools return a consistent dict shape consumable by existing action orchestration (`message`, optional structured fields such as `blocked`, `error`, or tool-specific metadata).
   - Rationale: avoids special-case handling in `act/observe` and simplifies testing.
   - Alternative considered: tool-specific raw payloads; rejected because it complicates runtime compose/trace behavior.

3. **Policy gate remains the single execution authority for risk**
   - Decision: High-risk tools are declared as high risk in manifests and continue to pass through `ExecutionPolicyGate` before handler execution.
   - Tool handlers still perform local argument/path validation for deterministic errors.
   - Rationale: preserves a single safety control plane while improving error clarity.
   - Alternative considered: duplicate policy logic in each tool; rejected due to drift risk.

4. **Introduce explicit env-driven tool exposure strategy**
   - Decision: keep `message_reply` always available; add baseline tool toggles using clear env keys and defaults documented in `.env.template`.
   - Rationale: allows progressive rollout and quick rollback without code reverts.
   - Alternative considered: always-on open tools; rejected because policy and deployment posture vary by environment.

5. **Codify parity boundaries in docs**
   - Decision: update `docs/agent-core-algorithm.md` and `repo_wiki.md` to describe baseline tool registration, risk classes, and blocked execution behavior.
   - Rationale: this is a runtime behavior change and must remain auditable.

## Risks / Trade-offs

- [Tool side-effects from write/shell capabilities] -> Mitigation: default-off toggles + existing high-risk policy gate + explicit blocked responses.
- [Behavior drift between docs and runtime flags] -> Mitigation: require same-change updates to `.env.template`, algorithm doc, and wiki.
- [Planner may over-select new tools once exposed] -> Mitigation: retain deterministic routing priorities and keep `message_reply` fallback.
- [Browser integration instability across environments] -> Mitigation: feature-flag browser tool and return deterministic unsupported/blocked responses when unavailable.

## Migration Plan

1. Add OpenSpec deltas for new capability (`builtin-open-tools-parity`) and modified capability (`skills-tool-orchestration`).
2. Implement new tool handler modules and wire manifests into `src/teambot/agents/tools/builtin.py`.
3. Define/update env toggles and policy-related keys in `.env.template`.
4. Add tests for registration matrix, policy deny/allow behavior, and normalized output envelopes.
5. Update runtime documentation (`docs/agent-core-algorithm.md`, `repo_wiki.md`).
6. Validate with `openspec validate align-open-tools-with-copaw-baseline` and relevant test suite.

Rollback strategy:
- Disable new tool exposure via env toggles.
- Revert registry wiring to `message_reply`-only behavior if required.
- Keep spec/docs trace to preserve why rollback happened.

## Open Questions

- Should `desktop_screenshot` and `send_file_to_user` be included in MVP parity or deferred to a follow-up change?
- What exact browser backend contract should TeamBot implement for `browser_use` in environments without GUI/browser automation support?
