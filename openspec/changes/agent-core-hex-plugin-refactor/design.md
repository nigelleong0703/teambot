## Context

The backend has already moved to a custom Agent Core runtime and provider-manager integration, but package boundaries are still blurred. Runtime orchestration, provider details, plugin lifecycle, and entrypoint concerns are partially mixed, which slows down future changes and increases accidental coupling.

This change establishes a stable architecture contract using `Modular Monolith + Hexagonal + Plugin` so development can remain fast (single deployable unit) while preserving clean dependency direction and extensibility.

## Goals / Non-Goals

**Goals:**
- Define explicit module boundaries for `agent_core`, `adapters`, `plugins`, and `interfaces`.
- Enforce one-way dependency direction from interfaces/adapters/plugins into core contracts.
- Keep runtime control flow in Agent Core while isolating provider/tool implementations behind ports.
- Standardize tool/skill plugin lifecycle with a shared registry and activation flow.
- Keep API behavior stable while improving internal architecture clarity.

**Non-Goals:**
- Splitting into microservices.
- Rewriting business planning logic or policy semantics.
- Introducing MCP integration in this change.
- Frontend/UI work.

## Decisions

1. **Adopt Modular Monolith package layout**
   - Decision: Keep one process/repo/deployable, but split code into architecture-focused modules.
   - Rationale: fastest delivery for a solo developer while avoiding service-distribution overhead.
   - Alternative considered: immediate microservices split; rejected due to operational complexity and premature boundaries.

2. **Use Hexagonal dependency boundaries**
   - Decision: core runtime/planning modules depend only on contracts (`ports`), never concrete provider/tool SDK implementations.
   - Rationale: makes provider/tool swap possible with minimal core changes and better unit testing.
   - Alternative considered: helper-based soft layering without strict contracts; rejected because it tends to regress into coupling.

3. **Unify tools and skills under plugin host lifecycle**
   - Decision: `plugins` package owns discovery, registration, activation, and execution lookup with normalized envelopes.
   - Rationale: aligns with open CoPaw-style extensibility while preserving policy gates and observability.
   - Alternative considered: keep skill and tool loading in separate ad-hoc paths; rejected due to duplicated lifecycle logic.

4. **Single composition root in interfaces/bootstrap**
   - Decision: runtime wiring (provider manager, plugin registries, policy gate, service) happens in one bootstrap entrypoint reused by API and CLI.
   - Rationale: avoids drift between API and CLI startup behavior.
   - Alternative considered: separate bootstrap logic in each interface; rejected because parity bugs are hard to detect.

5. **Boundary checks as tests**
   - Decision: add tests to assert import direction and lifecycle contracts.
   - Rationale: architecture intent must be executable, not only documented.
   - Alternative considered: documentation-only rules; rejected because rules decay without automated checks.

## Risks / Trade-offs

- [Directory moves can create temporary import breakage] → Mitigation: incremental shims and compatibility re-exports during migration.
- [Strict boundaries can feel slower at first] → Mitigation: keep contracts minimal and add pragmatic helper adapters where repeated patterns appear.
- [Plugin openness increases execution risk] → Mitigation: preserve policy gating before high-risk action execution.
- [Refactor noise may hide regressions] → Mitigation: keep API/CLI behavior tests and run full test suite after each migration batch.

## Migration Plan

1. Introduce target package layout and add compatibility re-exports for old import paths.
2. Move core contracts/runtime modules first, without changing request behavior.
3. Move provider/tool implementations into adapter/plugin packages and wire through contracts.
4. Centralize bootstrap wiring and align API + CLI entrypoints to shared composition.
5. Add/adjust boundary and lifecycle tests, then remove temporary shims where safe.
6. Validate change with OpenSpec and regression tests.

Rollback strategy:
- Keep transitional shims for critical imports until end-to-end tests pass.
- If regressions appear, restore previous import entrypoints while keeping new modules in place.

## Open Questions

- Should plugin activation be per-thread, per-agent, or process-global by default?
- Do we need hot-reload for active skill manifests in this phase, or only startup/load-time activation?
- Should boundary checks use a lightweight custom test only, or later adopt a dedicated lint rule/plugin?
