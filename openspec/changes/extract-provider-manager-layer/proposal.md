## Why

Provider endpoint handling is currently mixed into planner/model adapter code, which makes role-based routing and failover hard to evolve safely. We need a dedicated provider manager layer so endpoint concerns are isolated from Agent Core runtime logic.

## What Changes

- Introduce a dedicated provider manager capability for model provider configuration, client creation, role binding, and failover.
- Refactor planner-facing model access to depend on provider manager interfaces instead of endpoint/env parsing logic.
- Keep Agent Core runtime contracts unchanged while replacing internal provider wiring.
- Add compatibility mapping for existing env variables and define a stable provider configuration schema.
- Add tests for provider selection, fallback behavior, and normalized response parsing.

## Capabilities

### New Capabilities
- `provider-manager`: Unified provider management for endpoint config, role-based model binding, client registry, and failover routing.

### Modified Capabilities
- None.

## Impact

- Affected code: `src/teambot/agents/model_adapter.py`, `src/teambot/agents/planner.py`, and new `src/teambot/agents/providers/*` modules.
- Affected runtime behavior: provider/endpoint decisions move out of planner internals into dedicated manager layer.
- Affected configuration: standardized provider-role settings while preserving backward compatibility with existing env names.
- Affected tests: new unit/integration tests for provider routing, fallback, and output normalization.
