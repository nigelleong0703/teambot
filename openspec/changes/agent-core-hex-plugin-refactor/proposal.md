## Why

The current codebase has working agent features, but module boundaries are still inconsistent and responsibilities are mixed across runtime, providers, tools, and interfaces. We need a clear architecture baseline now so future feature work does not keep increasing coupling and maintenance cost.

## What Changes

- Introduce an explicit `Modular Monolith + Hexagonal + Plugin` architecture contract for the backend.
- Restructure runtime-facing code around stable ports/contracts in `agent_core` and provider/tool implementations in adapters/plugins.
- Standardize dependency direction: core modules do not import adapter implementations.
- Split entrypoints (`api`, `cli`) from agent runtime internals and enforce a single composition root.
- Formalize plugin lifecycle for tools and skills (discovery, registration, activation, execution).

## Capabilities

### New Capabilities
- `modular-hex-plugin-architecture`: Architecture boundary rules, composition root rules, and module dependency constraints for backend agent code.

### Modified Capabilities
- `agent-core-runtime`: Runtime execution flow remains custom, but module ownership and composition boundaries are tightened.
- `langchain-adapter-layer`: LangChain/provider integrations are constrained to adapter modules behind ports.
- `skills-tool-orchestration`: Tools and skills adopt an explicit plugin lifecycle and unified plugin registry contract.

## Impact

- Affected code: `src/teambot/agents/*`, `src/teambot/interfaces/*`, and related configuration/bootstrap modules.
- Affected testing: add boundary/contract tests for import direction and plugin lifecycle behavior.
- Affected development workflow: new modules and naming conventions for future changes.
- External APIs are expected to remain stable; this is an internal architecture refactor.
