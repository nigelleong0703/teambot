## Why

The current runtime relies on LangGraph for primary orchestration, which constrains open-ended tool planning and makes CoPaw-style skill-driven execution harder to control. We need a self-owned agent core with explicit control flow while still reusing LangChain’s model/tool ecosystem.

## What Changes

- **BREAKING**: Replace LangGraph as the main orchestration runtime for agent execution.
- Introduce a custom Agent Core loop (`route -> plan -> act -> observe -> finish`) with explicit state transitions and termination guards.
- Add a LangChain adapter layer for multi-provider model calls, structured output parsing, and tool invocation.
- Separate skill lifecycle management from tool execution framework while defining a shared invocation contract.
- Keep existing entry surfaces stable via compatibility imports while moving implementation to the new core runtime.
- Update runtime and integration tests to validate behavior parity and migration safety.

## Capabilities

### New Capabilities
- `agent-core-runtime`: Ownable open-loop runtime with deterministic control flow, step budget, and safety gates.
- `langchain-adapter-layer`: Unified LangChain-based model/tool adapters for multiple providers.
- `skills-tool-orchestration`: Clear separation of skills lifecycle and tool framework with coordinated execution policy.

### Modified Capabilities
- None.

## Impact

- Affected code: `src/teambot/agents/core/*`, `src/teambot/agents/planner.py`, `src/teambot/agents/skills/*`, and compatibility modules under `src/teambot/agents/`.
- Affected dependencies: LangChain packages become first-class runtime dependencies; LangGraph removed from primary execution path.
- Affected APIs: Internal runtime contracts change; external FastAPI ingress/event contracts remain stable.
- Affected testing: Graph-centric tests transition to core-loop + adapter + lifecycle integration tests.
