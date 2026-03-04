# TeamBot Backend Architecture Boundaries

## 1. Module Ownership

- `src/teambot/agent_core`
  - Core contracts only (`ports` / protocol-like abstractions).
  - No provider SDK, no tool implementation details.
- `src/teambot/adapters`
  - Provider and tool adapter wiring.
  - Translate external SDK/API behavior to core contracts.
- `src/teambot/plugins`
  - Unified plugin host lifecycle: registration, activation, invocation.
  - Compose skill and tool actions into one action surface.
- `src/teambot/interfaces`
  - API/CLI composition root and process entrypoints.
  - No business planning logic.
- `src/teambot/agents`
  - Runtime implementation, progressively aligned to the new boundaries.
  - Backward-compatible import shims remain allowed during migration.

## 2. Allowed Dependency Direction

Allowed:

- `interfaces -> agents/agent_core/adapters/plugins`
- `agents(core/runtime) -> agent_core contracts`
- `adapters -> agent_core contracts`
- `plugins -> agent_core contracts`

Disallowed:

- `agent_core -> adapters`
- `agent_core -> provider/tool SDK wrappers`
- `agents/core -> direct provider SDK wrappers`

## 3. Composition Root Rule

- Shared composition root: `src/teambot/interfaces/bootstrap.py`.
- `main.py` and `cli.py` MUST build runtime dependencies through this bootstrap.
- Runtime wiring should not diverge between API and CLI entrypoints.

## 4. Migration Rule

- Existing paths under `teambot.agents.*` remain compatibility surfaces.
- New features should prefer `agent_core`, `adapters`, `plugins`, and `interfaces`.
- When moving modules, keep compatibility re-exports until tests and callers are updated.
