# CoPaw Path C Internal Runtime Design

## 1. Context

TeamBot currently runs a custom ReAct loop with unified action execution, but internal runtime composition is still MVP-style:
- Built-in tools are mostly assembled in one file.
- Skills lifecycle exists but initialization and runtime loading semantics are not fully CoPaw-like.
- MCP tooling is not managed through a dedicated runtime manager and bridge.

This design adopts **Path C**: mirror CoPaw internal mechanisms for tools, skills, and MCP while keeping current external API/CLI behavior unchanged (Step 1 only).

## 2. Scope

### In Scope (Step 1)
- Internal tool runtime management:
  - explicit runtime tool subset registration
  - namesake conflict strategy (`skip|override|raise|rename`)
  - tool profile-driven activation
- Skill runtime lifecycle alignment:
  - `builtin/customized/active` directories with active-only runtime loading
  - deterministic sync semantics
- MCP runtime management:
  - manager lifecycle (`init/reload/close`)
  - MCP tool bridge into TeamBot tool/action surface
- Documentation and tests for new runtime behavior

### Out of Scope (Step 2)
- New external API/CLI commands for runtime profile switching, skills config UX, and MCP operations
- UI/console parity behavior

## 3. Target Internal Architecture

### 3.1 New Runtime Assembly Layer
- Add internal orchestrator: `src/teambot/agents/runtime/orchestrator.py`
- Orchestrator owns runtime component assembly:
  - skill loader
  - tool builder
  - MCP manager + bridge
  - plugin host binding
- `AgentService` becomes thin shell around orchestrator output.

### 3.2 Tooling Modules (CoPaw-like layering)
- `src/teambot/agents/tools/catalog.py`
  - canonical builtin tool definitions + manifests
- `src/teambot/agents/tools/profiles.py`
  - named profiles (`minimal`, `external_operation`, `full`)
- `src/teambot/agents/tools/namesake.py`
  - conflict strategy engine
- `src/teambot/agents/tools/runtime_builder.py`
  - builds runtime tool registry from profile + strategy + optional MCP tools
- Keep implementation files (e.g. `external_operation_tools.py`) separate from registration logic.

### 3.3 Skills Modules (active-only runtime)
- Keep and align `src/teambot/skills/manager.py` semantics:
  - `builtin`: repo baseline packs
  - `customized`: workspace customization
  - `active`: runtime-loaded set
- Ensure runtime only consumes active set.
- Sync functions remain explicit operations; startup should not silently mutate active state.

### 3.4 MCP Modules
- Add `src/teambot/mcp/manager.py`
  - load config, open clients, reload, close
- Add `src/teambot/mcp/bridge.py`
  - map MCP tools into `ToolRegistry` manifests/handlers
- Add `src/teambot/mcp/config.py`
  - parse and validate MCP env/config payloads

## 4. Runtime Flow (After Refactor)

1. `AgentService` initialization
- Read runtime settings (tool profile, namesake strategy, skills dirs, MCP settings).
- Build orchestrator.
- Call orchestrator to assemble runtime objects.

2. Runtime assembly
- Load active skills into skill registry.
- Build builtin tool registry from profile.
- Resolve namesake conflicts deterministically.
- Initialize MCP manager and bridge MCP tools into tool registry.
- Bind all to `PluginHost` and build graph.

3. Request handling
- Existing ReAct loop remains unchanged.
- Action dispatch now operates over richer but deterministic action surface.

4. Reload
- `service.reload_runtime()` rebuilds all runtime components using orchestrator.

## 5. Config Model (Step 1 Internal)

Primary keys:
- `TOOLS_PROFILE` (`minimal|external_operation|full`)
- `TOOLS_NAMESAKE_STRATEGY` (`skip|override|raise|rename`)
- `MCP_ENABLED` (`true|false`)
- `MCP_CONFIG_PATH` or `MCP_SERVERS_JSON`

Policy keys remain unchanged:
- `ALLOW_HIGH_RISK_ACTIONS`
- `HIGH_RISK_ALLOWED_ACTIONS`

## 6. Error Handling Policy

- Tool namesake conflict:
  - strategy-driven; no hidden random order behavior.
- MCP init failure:
  - do not crash service by default; log degraded mode and continue with builtin tools.
- Active skills missing:
  - deterministic warning; runtime still starts with tools.

## 7. Testing Strategy

### Unit
- namesake strategy behavior
- profile registry composition
- active-only skill loading
- MCP bridge manifest mapping

### Integration
- runtime assembly with/without MCP
- conflict cases across builtin/MCP tools
- reload behavior preserving deterministic action surface

### Regression
- existing core loop tests remain green
- policy gate behavior unchanged for high-risk actions

## 8. Migration and Rollback

### Migration
1. Add new runtime modules and tests.
2. Wire `AgentService` to orchestrator.
3. Switch `.env.template` to new internal config keys.
4. Update docs.

### Rollback
- Revert `AgentService` to previous direct registry composition.
- Keep core graph untouched.
- Set `TOOLS_PROFILE=minimal` for emergency runtime reduction.

## 9. Risks

- Larger internal refactor surface may temporarily increase assembly bugs.
- Introducing namesake strategies can expose previously hidden name collisions.
- MCP partial failures need clear degraded-state observability.

## 10. Success Criteria

- Service boots and processes requests with same external interface.
- Action surface is profile-driven and deterministic.
- Skills runtime loads active set only.
- MCP tools can be injected/reloaded without breaking core loop.
- Tests pass and docs reflect new internals.

