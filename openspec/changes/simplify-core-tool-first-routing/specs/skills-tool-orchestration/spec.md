## MODIFIED Requirements

### Requirement: Runtime SHALL Use Unified Action Contract
The runtime SHALL resolve both skill and tool actions through one normalized action registry contract, and default conversational replies SHALL be represented as tool actions.

#### Scenario: Default conversational request
- **WHEN** user message does not match higher-priority deterministic routing rules
- **THEN** runtime selects `general_reply` as tool action when available
- **THEN** action execution uses the same orchestration envelope as skills

### Requirement: High-Risk Actions SHALL Be Policy-Gated
The orchestration layer SHALL apply execution policy gates before running high-risk actions.

#### Scenario: High-risk action request
- **WHEN** selected action has high-risk level
- **THEN** policy gate evaluates allow/deny before invocation
- **THEN** denied action returns safe blocked output without execution
