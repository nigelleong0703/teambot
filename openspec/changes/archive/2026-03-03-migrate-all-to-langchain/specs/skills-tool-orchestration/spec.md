## ADDED Requirements

### Requirement: Skills Lifecycle SHALL Be Managed Separately From Tool Execution
The system SHALL manage skill discovery/activation independently from low-level tool execution adapters.

#### Scenario: Skill activation refresh
- **WHEN** active skills are reloaded
- **THEN** skill availability updates without rebuilding tool adapter implementations
- **THEN** runtime sees updated skill manifests on next request

### Requirement: Runtime SHALL Use Unified Action Contract
The runtime SHALL resolve both registered skills and tool-backed actions through one normalized action selection contract.

#### Scenario: Planned action resolution
- **WHEN** planner selects an action name
- **THEN** runtime resolves it against active action registry (skills and tool-backed actions)
- **THEN** runtime executes with consistent input/output envelope

### Requirement: High-Risk Actions SHALL Be Policy-Gated
The orchestration layer SHALL apply execution policy gates before running high-risk actions.

#### Scenario: High-risk action request
- **WHEN** a planned action is classified as high-risk
- **THEN** policy gate evaluates allow/deny and required constraints
- **THEN** denied actions return a safe blocked result without execution
