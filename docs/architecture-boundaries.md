# TeamBot Backend Architecture Boundaries

Canonical structure reference: `docs/code-structure.md`.

## 1. Module Ownership

- `src/teambot/contracts`
  - Shared protocols and thin interfaces only.
  - No provider SDK calls, no runtime flow, no tool implementations.
- `src/teambot/agent`
  - ReAct loop, runtime owner, application service, prompt assembly, and runtime orchestrator.
- `src/teambot/actions`
  - Executable actions.
  - Includes model-callable tools and deterministic event handlers.
- `src/teambot/providers`
  - Provider manager and provider client implementations.
- `src/teambot/skills`
  - Skill docs lifecycle and reasoner context assembly.
- `src/teambot/mcp`
  - MCP configuration, manager, and tool bridge.
- `src/teambot/app`
  - API/CLI entrypoints and composition root.
- `src/teambot/domain`
  - TeamBot core objects and storage models.

## 2. Allowed Dependency Direction

Allowed:

- `app -> agent/actions/providers/skills/mcp/domain/contracts`
- `agent -> actions/providers/skills/mcp/domain/contracts`
- `actions -> domain/contracts`
- `providers -> contracts`
- `skills -> domain/contracts`
- `mcp -> actions/providers/contracts`

Disallowed:

- `domain -> agent/actions/providers/skills/mcp`
- `providers -> agent`
- `contracts -> runtime implementations`
- `contracts -> provider SDK wrappers`

## 3. Composition Root Rule

- Shared composition root: `src/teambot/app/bootstrap.py`.
- `main.py`, `cli.py`, and future TUI entrypoints MUST build runtime dependencies through this bootstrap.
- Runtime wiring should not diverge between entrypoints.

## 4. Runtime Cleanup Rule

- Internal imports should target implementation modules directly.
- New ReAct loop behavior belongs under `agent/`.
- New tools or deterministic handlers belong under `actions/`.
- New provider integrations belong under `providers/`.
- New skill lifecycle/context code belongs under `skills/`.
- New MCP bridge/config/runtime code belongs under `mcp/`.
