## MODIFIED Requirements

### Requirement: Runtime SHALL Use Unified Action Contract
The runtime SHALL resolve both registered skills and built-in open tools through one normalized action selection contract, including CoPaw-aligned tool names and deterministic fallback behavior.

#### Scenario: Planned action resolution for built-in open tool
- **WHEN** planner or deterministic router selects a registered built-in open tool action
- **THEN** runtime resolves it against the active action registry without a separate code path
- **THEN** runtime executes it with the same input/output envelope used for skills

#### Scenario: Selected action not available
- **WHEN** selected action is absent from active action registry
- **THEN** runtime falls back to default action resolution rules
- **THEN** runtime does not terminate with unresolved-action failure

### Requirement: High-Risk Actions SHALL Be Policy-Gated
The orchestration layer SHALL apply execution policy gates before running high-risk actions, and denied actions SHALL return a safe blocked result without invoking underlying side-effect handlers.

#### Scenario: High-risk action request denied
- **WHEN** a selected high-risk tool action is not allowed by policy gate
- **THEN** policy gate returns deny before tool handler invocation
- **THEN** runtime records a blocked observation and returns safe blocked output

#### Scenario: High-risk action request allowed
- **WHEN** a selected high-risk tool action is explicitly allowed by policy gate
- **THEN** runtime invokes the handler through normal action execution path
- **THEN** runtime records execution trace using the same structure as other actions
