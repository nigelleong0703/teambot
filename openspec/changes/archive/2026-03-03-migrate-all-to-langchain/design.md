## Context

The repository currently uses LangGraph as the primary orchestration engine while skills are managed separately. This works for a closed set of deterministic transitions, but it is less suitable for CoPaw-style open-ended execution where action routing, policy gating, and dual-model decisions need first-class control in code. The target architecture keeps the existing external API stable while replacing internal orchestration with a custom Agent Core runtime and LangChain adapters.

## Goals / Non-Goals

**Goals:**
- Replace LangGraph-based runtime orchestration with a custom Agent Core loop.
- Use LangChain as infrastructure layer for model and tool adapters.
- Preserve existing ingress and reply contracts.
- Support multi-provider model routing and dual-model decisions (router model + agent model).
- Keep skills lifecycle explicit and separate from tool adapter internals.

**Non-Goals:**
- Full CoPaw parity in one change (channels/cron/memory compaction full stack).
- Unbounded unrestricted tool execution without policy gates.
- Reintroducing MCP integration in this migration change.

## Decisions

1. **Own the runtime loop in `agent core` (not LangGraph)**
   - Rationale: explicit control over step transitions, guards, and fallback behavior.
   - Alternative considered: keep LangGraph and wrap custom nodes. Rejected because graph runtime remains the control bottleneck.

2. **Adopt LangChain adapters for providers/tools only**
   - Rationale: leverage ecosystem while avoiding high-level black-box agent executors.
   - Alternative considered: full custom provider SDK clients. Rejected due to duplicated integration cost.

3. **Split `skills` and `tools` as separate framework layers**
   - Rationale: skills lifecycle (discover/activate/docs) and tool execution (read/exec/web/etc.) evolve at different rates and risk profiles.
   - Alternative considered: merge into one registry. Rejected due to blurred governance and policy scope.

4. **Dual-model decision path**
   - Rationale: lower-cost router model handles common routing, stronger agent model is invoked only when needed.
   - Alternative considered: single strong model for all steps. Rejected due to cost and latency.

5. **Compatibility import surface during migration**
   - Rationale: keep existing imports/tests stable while implementation moves into new core modules.
   - Alternative considered: hard cutover with immediate path changes. Rejected due to avoidable break risk.

## Risks / Trade-offs

- [Runtime regression in complex loops] -> Mitigation: golden-path integration tests for multi-step chains and fallback routes.
- [Provider behavior differences across models] -> Mitigation: strict structured output validation and deterministic fallback planner.
- [Policy gating too strict/too permissive initially] -> Mitigation: start with explicit allowlist and audit logs, then tune by observed traces.
- [Migration complexity while maintaining compatibility] -> Mitigation: phase-by-phase cutover with compatibility shims and deprecation window.

## Migration Plan

1. Add new Agent Core loop modules and LangChain adapter interfaces behind existing service façade.
2. Migrate planning and execution path from graph invocation to core loop invocation.
3. Introduce unified action registry bridging skills manifests and tool-backed actions.
4. Add policy gate layer for high-risk actions.
5. Switch default runtime path to Agent Core, keep compatibility imports.
6. Remove LangGraph from primary runtime dependencies after tests pass and behavior parity is confirmed.

Rollback strategy:
- Keep previous orchestration entrypoint behind a feature flag until rollout confidence is achieved.
- If regressions appear, route traffic back to legacy path while preserving new adapter code for iterative fixes.

## Open Questions

- Which concrete tool actions are in scope for v1 of unified action registry (`read`, `exec`, `search`, others)?
- What exact provider matrix is required at launch (OpenAI-compatible + Anthropic + local)?
- Should policy gate decisions be purely static config first, or include model-assisted risk classification in phase 1?
