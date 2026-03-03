## Context

The codebase already migrated to Agent Core runtime and LangChain adapters, but provider concerns (env parsing, endpoint selection, adapter instantiation) still sit too close to planner logic. This coupling increases change risk whenever new providers, role bindings, or failover rules are introduced. A dedicated provider manager layer is needed to separate concerns and make provider behavior testable in isolation.

## Goals / Non-Goals

**Goals:**
- Introduce a dedicated provider manager package under `agents/providers`.
- Move provider config parsing and role binding out of planner internals.
- Expose a stable provider-facing interface to planner (`router_model` and `agent_model`).
- Add deterministic fallback/failover policy per model role.
- Keep external API behavior and Agent Core runtime loop unchanged.

**Non-Goals:**
- Changing business routing logic in `RulePlanner`.
- Reworking skills/tool policy frameworks in this change.
- Adding new external tool providers beyond existing model providers.

## Decisions

1. **Create `providers` package with clear boundaries**
   - Modules: `config`, `base`, `clients`, `registry`, `router`, `normalize`.
   - Rationale: predictable extension points and isolated tests.

2. **Planner depends on provider manager interface, not env vars**
   - Rationale: planner should focus on planning semantics, not transport configuration.
   - Alternative: keep env parsing in planner with helper functions. Rejected due to layering leakage.

3. **Use role-based model binding (`router_model`, `agent_model`)**
   - Rationale: makes dual-model cost/performance policy explicit and auditable.
   - Alternative: infer role from model names. Rejected as brittle and implicit.

4. **Implement bounded failover sequence**
   - Rationale: deterministic behavior and predictable latency/cost.
   - Alternative: unbounded retries. Rejected due to latency explosion and observability issues.

5. **Keep compatibility fallback for existing env names**
   - Rationale: avoid abrupt breakage in current operator setups.
   - Alternative: hard cutover to new env schema. Rejected for migration risk.

## Risks / Trade-offs

- [Provider abstractions overfit current providers] → Mitigation: keep base interface minimal and response normalization explicit.
- [Failover masks root-cause errors] → Mitigation: include provider attempt trace in structured errors/logs.
- [Migration complexity in planner wiring] → Mitigation: phase rollout with adapter shim and focused tests per role.

## Migration Plan

1. Add `agents/providers` package with base contracts and provider config loader.
2. Move model client creation from current adapter path into provider manager registry/router.
3. Refactor planner to request role-bound model invocations from provider manager.
4. Keep `model_adapter.py` as compatibility shim until callers fully migrate.
5. Add tests for role binding, failover, and response normalization.
6. Deprecate direct endpoint parsing in planner after parity verification.

Rollback strategy:
- Keep compatibility adapter path behind a feature switch while new provider manager is validated.
- If regressions occur, temporarily route planner calls through legacy adapter construction.

## Open Questions

- Should provider failover policy be configured per role only, or per role + task type?
- What is the minimum normalized usage schema required for cost accounting?
- Do we need provider-level circuit breaker state in this phase or a later phase?
