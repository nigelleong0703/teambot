## 1. Runtime Semantics Separation

- [x] 1.1 Introduce action-oriented state helpers that support `selected_action/action_input/action_output` while preserving compatibility reads/writes for legacy `selected_skill/skill_input/skill_output`.
- [x] 1.2 Refactor router reason stage to use action naming and keep deterministic event-handler precedence before reasoner model calls.
- [x] 1.3 Extract deterministic handlers for `/todo` and reaction events from executable skill registration path into explicit event-handler routing logic.

## 2. Tool-Only Model Execution Surface

- [x] 2.1 Ensure reasoner tool spec builder exposes only registered tools to model tool-calling.
- [x] 2.2 Keep deterministic handler execution out of model tool schema while preserving normalized runtime observation and trace shape.
- [x] 2.3 Add regression tests that verify model cannot invoke deterministic handlers as tool calls.

## 3. Skill Context Injection

- [x] 3.1 Add a bounded skill-context assembler that loads active skills and builds compact summary + bounded detail payload sections.
- [x] 3.2 Inject skill context into reasoner request construction (system prompt extension and payload fields) with safe empty-skill fallback.
- [x] 3.3 Add routing/reasoner tests validating skill-context-aware request construction and fallback behavior.

## 4. CLI Skills Management Parity

- [x] 4.1 Extend interactive CLI command parser/help with `/skills`, `/skills sync`, `/skills enable <name>`, `/skills disable <name>`.
- [x] 4.2 Wire CLI skills commands to existing `SkillService` lifecycle operations and call runtime reload after mutations.
- [x] 4.3 Add CLI command tests for listing/sync/enabling/disabling behavior and invalid command input handling.

## 5. Naming and Documentation Alignment

- [x] 5.1 Rename planner-facing runtime terminology to reasoner/decision-model terminology in runtime modules (with compatibility aliases where needed).
- [x] 5.2 Update `docs/agent-core-algorithm.md` to reflect new behavior contract (skills as context, tools as executable, deterministic handlers).
- [x] 5.3 Update `repo_wiki.md`, `docs/README.md`, and `docs/code-structure.md` for module responsibility and runtime flow naming changes.

## 6. Verification and Rollout Safety

- [x] 6.1 Run targeted tests for router/runtime/skills/CLI behavior and fix regressions.
- [x] 6.2 Run full `pytest -q` and capture any intentionally deferred verification if failures are unrelated.
- [x] 6.3 Validate CLI runtime manually with external-operation profile (`/tools`, `/skills` flows, and a tool-call prompt) before merge.
