## Why

Current runtime terminology and behavior mix `skills`, `tools`, and event handlers in one execution surface, which makes routing behavior hard to reason about and easy to misinterpret. We need a clearer contract so model-calling, deterministic event handling, and skill knowledge injection are separated by purpose.

## What Changes

- Separate runtime semantics:
  - `tools` are executable model-callable operations.
  - `skills` are knowledge/context documents, not executable actions.
  - event-driven handlers (for example reaction and `/todo`) are deterministic handlers, not skills.
- Move built-in `create_task` and `handle_reaction` behavior to deterministic handler routing rather than skill registry execution.
- Restrict model tool-calling surface to true tools only, and inject active skill docs into reasoning context (system prompt/payload contract).
- Rename planner-facing runtime terminology toward reasoning semantics (`planner` -> `reasoner`/decision-model naming in runtime-facing code/docs).
- Add CLI skills management parity commands:
  - `/skills`
  - `/skills sync`
  - `/skills enable <name>`
  - `/skills disable <name>`
- Preserve backward compatibility during migration (state key aliases, compatibility adapters) and then clean up once tests/docs are updated.

## Capabilities

### New Capabilities

- `cli-skills-management`: Interactive CLI commands to inspect/sync/enable/disable skills consistently with existing HTTP skill lifecycle APIs.

### Modified Capabilities

- `skills-tool-orchestration`: Change requirement contract so skills are runtime reasoning context resources rather than executable actions; executable surface is tool-only plus deterministic handlers.
- `agent-core-runtime`: Update reason/act/observe contract to use action/reasoning semantics and deterministic event handler precedence.

## Impact

- Affected code:
  - `src/teambot/agents/core/*` (router, state fields, runtime flow naming)
  - `src/teambot/agents/skills/*` (runtime usage semantics)
  - `src/teambot/app/cli.py` (interactive skills commands)
  - prompt/reasoning context assembly path
- Affected tests:
  - router/planner integration tests
  - skill lifecycle/runtime tests
  - CLI command behavior tests
- Affected docs:
  - `docs/agent-core-algorithm.md`
  - `repo_wiki.md`
  - `docs/README.md` and `docs/code-structure.md` (if module responsibilities change)
