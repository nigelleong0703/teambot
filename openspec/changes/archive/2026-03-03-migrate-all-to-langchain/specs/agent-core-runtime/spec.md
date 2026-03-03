## ADDED Requirements

### Requirement: Agent Core SHALL Own Runtime Control Flow
The system SHALL execute agent requests through a custom runtime loop that does not depend on LangGraph graph compilation or graph invocation at runtime.

#### Scenario: Runtime starts a request
- **WHEN** an inbound event is accepted by AgentService
- **THEN** the request is executed by the custom Agent Core loop entrypoint
- **THEN** no LangGraph runtime object is required to process the event

### Requirement: Agent Core SHALL Enforce Deterministic Step Guards
The runtime SHALL enforce configurable step limits and termination conditions for every request.

#### Scenario: Step limit reached
- **WHEN** loop iteration count reaches configured `react_max_steps`
- **THEN** the runtime marks execution as finished
- **THEN** the runtime composes a safe fallback reply if no final message exists

### Requirement: Agent Core SHALL Emit Structured Execution Trace
The runtime SHALL append structured per-step observations to state for diagnostics and testing.

#### Scenario: Skill execution produces observation
- **WHEN** a skill/tool execution returns output
- **THEN** the runtime appends a step trace entry including selected action and observation summary
- **THEN** the trace is available in final state for assertions
