## 1. OpenSpec And Runtime Simplification

- [x] 1.1 Add spec deltas for `agent-core-runtime`, `langchain-adapter-layer`, and `skills-tool-orchestration`
- [x] 1.2 Refactor `reason` stage to deterministic action routing without planner dependency
- [x] 1.3 Remove planner wiring from runtime construction (`graph` + `service`)

## 2. Tool-First Message Generation

- [x] 2.1 Implement model-backed `general_reply` tool prompt contract (`{ "message": string }`)
- [x] 2.2 Keep deterministic fallback reply when provider is unavailable or returns invalid output
- [x] 2.3 Keep policy gate behavior unchanged for all actions

## 3. Validation And Docs

- [x] 3.1 Update tests that currently depend on planner injection behavior
- [x] 3.2 Update `docs/agent-core-algorithm.md` with new flow + prompt sections
- [x] 3.3 Update `repo_wiki.md` to prevent flow drift
- [x] 3.4 Run `openspec validate simplify-core-tool-first-routing` and relevant test suite
