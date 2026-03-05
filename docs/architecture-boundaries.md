# TeamBot Backend Architecture Boundaries

Canonical structure reference: `docs/code-structure.md`.

## 1. Module Ownership

- `src/teambot/agent_core`
  - Core contracts only (`ports` / protocol-like abstractions).
  - No provider SDK, no tool implementation details.
- `src/teambot/plugins`
  - Unified plugin host lifecycle: registration, activation, invocation.
  - Compose skill and tool actions into one action surface.
- `src/teambot/interfaces`
  - API/CLI composition root and process entrypoints.
  - No business planning logic.
- `src/teambot/agents`
  - Runtime implementation (`react_agent`, `core`, `tools`, `skills`, `providers`, `mcp`).
  - Single source of runtime assembly and execution.

## 2. Allowed Dependency Direction

Allowed:

- `interfaces -> agents/agent_core/plugins`
- `agents(core/runtime) -> agent_core contracts`
- `plugins -> agent_core contracts`

Disallowed:

- `agent_core -> provider/tool SDK wrappers`
- `agents/core -> direct provider SDK wrappers`

## 3. Composition Root Rule

- Shared composition root: `src/teambot/interfaces/bootstrap.py`.
- `main.py` and `cli.py` MUST build runtime dependencies through this bootstrap.
- Runtime wiring should not diverge between API and CLI entrypoints.

## 4. Runtime Cleanup Rule

- No compatibility re-export layers for `service`/`graph`/provider-tool adapters.
- Internal imports should target implementation modules directly.
- New features should extend `agents/react_agent.py` and runtime submodules, not add alias packages.
