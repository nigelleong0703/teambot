## 1. Establish Target Module Boundaries

- [x] 1.1 Create or align backend package layout for `agent_core`, `adapters`, `plugins`, and `interfaces`
- [x] 1.2 Add compatibility re-exports/shims for existing import paths to avoid immediate breakage
- [x] 1.3 Define core ports/contracts for model, tool, and skill interactions under Agent Core
- [x] 1.4 Add architecture boundary notes in developer docs (module ownership + allowed dependency direction)

## 2. Move Runtime And Adapter Responsibilities

- [x] 2.1 Refactor runtime/planner modules to consume only core contracts
- [x] 2.2 Move provider-specific model access code into adapter modules behind contracts
- [x] 2.3 Ensure tool execution adapters are isolated from core runtime loop code
- [x] 2.4 Remove direct core imports of provider/tool SDK wrappers after parity verification

## 3. Implement Unified Plugin Lifecycle

- [x] 3.1 Implement plugin host/registry responsibilities for discovery, registration, and activation
- [x] 3.2 Wire tool plugins and skill manifests into the unified registry contract
- [x] 3.3 Ensure runtime action resolution uses plugin registry lookups with normalized envelopes
- [x] 3.4 Keep high-risk action policy gating enforced before plugin execution

## 4. Compose Interfaces And Validate

- [x] 4.1 Build a single composition root used by both API startup and CLI startup
- [x] 4.2 Verify CLI and API behavior parity for message and reaction flows
- [x] 4.3 Add/update tests for boundary direction, plugin lifecycle, and regression behavior
- [x] 4.4 Run OpenSpec validation and confirm change is apply-ready
