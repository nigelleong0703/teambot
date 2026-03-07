## MODIFIED Requirements

### Requirement: Agent Core SHALL Own Runtime Control Flow
The system SHALL execute agent requests through a custom runtime loop with explicit reason/act/observe/compose stages, where deterministic event-handler routing precedes reasoner model selection.

#### Scenario: Runtime starts a request
- **WHEN** an inbound event is accepted by AgentService
- **THEN** the request is executed by the custom Agent Core loop entrypoint
- **THEN** deterministic event-handler checks run before reasoner model tool-selection

### Requirement: Agent Core SHALL Emit Structured Execution Trace
The runtime SHALL append structured per-step observations to state for diagnostics and testing using action-oriented semantics, while preserving compatibility aliases during migration.

#### Scenario: Action execution produces observation
- **WHEN** a tool action or deterministic handler execution returns output
- **THEN** the runtime appends a step trace entry including selected action and observation summary
- **THEN** the trace is available in final state for assertions

## ADDED Requirements

### Requirement: Agent Core SHALL Inject Active Skill Context Into Reasoning Inputs
The runtime SHALL inject active skill context into reasoner inputs through a bounded prompt/payload contract without exposing skills as executable model-call actions.

#### Scenario: Reasoner request built with active skills
- **WHEN** reason stage prepares reasoner request and active skills exist
- **THEN** request includes a compact skill index in system prompt extension
- **THEN** request payload may include bounded skill detail excerpts
- **THEN** executable model tool schema includes only registered tools

#### Scenario: No active skills available
- **WHEN** reason stage prepares reasoner request and active skills are empty
- **THEN** runtime omits skill context sections safely
- **THEN** reasoner execution continues with baseline prompt/payload contract
