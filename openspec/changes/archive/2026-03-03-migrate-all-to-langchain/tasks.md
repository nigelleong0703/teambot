## 1. Core Runtime Cutover

- [x] 1.1 Implement custom Agent Core loop entrypoint (`route -> plan -> act -> observe -> finish`) and wire it into `AgentService`
- [x] 1.2 Replace LangGraph runtime invocation path with core-loop invocation while preserving current reply contract
- [x] 1.3 Add deterministic termination guards (max steps, done flag, safe fallback reply)
- [x] 1.4 Add structured execution trace collection and expose it for tests

## 2. LangChain Adapter Layer

- [x] 2.1 Introduce model adapter interface for router/agent planner calls using LangChain clients
- [x] 2.2 Add multi-provider configuration mapping without changing core-loop code
- [x] 2.3 Implement structured planner output validation and fallback-to-rule behavior
- [x] 2.4 Migrate existing reasoning planner integration to adapter-backed implementation

## 3. Skills And Tool Orchestration

- [x] 3.1 Separate skills lifecycle services from tool execution framework boundaries
- [x] 3.2 Implement unified action resolution contract across skills and tool-backed actions
- [x] 3.3 Add high-risk action policy gate before execution
- [x] 3.4 Keep compatibility import surfaces stable during migration

## 4. Validation And Cleanup

- [x] 4.1 Add/upgrade integration tests for multi-step loop, fallback, and policy gate behavior
- [x] 4.2 Verify external API behavior parity for message and reaction flows
- [x] 4.3 Remove LangGraph from primary runtime dependency path and docs
- [x] 4.4 Document migration notes and operator configuration updates
