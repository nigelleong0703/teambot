# builtin-open-tools-parity Specification

## Purpose
TBD - created by archiving change align-open-tools-with-copaw-baseline. Update Purpose after archive.
## Requirements
### Requirement: Runtime SHALL Register CoPaw-Aligned External-Operation Tools
TeamBot runtime SHALL provide external-operation tools aligned to CoPaw baseline, including `read_file`, `write_file`, `edit_file`, `execute_shell_command`, `browser_use`, and `get_current_time`, while preserving `message_reply` inside the built-in tool surface as default conversational action.

#### Scenario: Baseline tools enabled
- **WHEN** runtime builds the built-in tool registry with baseline tools enabled
- **THEN** registry contains all required CoPaw-aligned tool names
- **THEN** each tool is invokable through the same action execution path as existing built-in actions

### Requirement: External-Operation Tool Responses SHALL Use a Normalized Output Envelope
All external-operation tool handlers SHALL return deterministic dict-shaped outputs with a user-facing `message` field and optional structured fields (`blocked`, `error`, or tool metadata) instead of raising uncaught exceptions into runtime flow.

#### Scenario: Tool success response
- **WHEN** an external-operation tool executes successfully
- **THEN** runtime receives a dict result containing `message`
- **THEN** `observe` and `compose_reply` can consume the output without tool-specific branching

#### Scenario: Tool failure response
- **WHEN** an external-operation tool encounters invalid input or runtime errors
- **THEN** the handler returns a safe deterministic error message in the normalized envelope
- **THEN** runtime continues without process crash

### Requirement: High-Risk External-Operation Tools SHALL Be Classified for Policy Gate
`execute_shell_command`, `write_file`, and `edit_file` SHALL be registered as high-risk actions so that execution is subject to policy gating before handler invocation.

#### Scenario: High-risk classification
- **WHEN** built-in tools are registered
- **THEN** manifests for shell and mutating file tools declare high-risk level
- **THEN** execution policy gate evaluates them before runtime invokes handlers

### Requirement: Tool Exposure SHALL Be Environment-Configurable
Runtime SHALL support environment-driven tool surface profiles and namesake strategy, with defaults documented in `.env.template`.

#### Scenario: Minimal profile selected
- **WHEN** `TOOLS_PROFILE=minimal`
- **THEN** runtime registers `message_reply` and excludes external-operation tools
- **THEN** runtime fallback behavior remains available via `message_reply`

#### Scenario: External operation profile selected
- **WHEN** `TOOLS_PROFILE=external_operation`
- **THEN** runtime registers CoPaw-aligned external-operation tool subset
- **THEN** each tool is available through the unified action contract

### Requirement: Namesake Strategy SHALL Control Tool Name Conflicts
Runtime SHALL apply configured namesake strategy (`skip`, `override`, `raise`, `rename`) when tool name collisions occur during runtime registration.

#### Scenario: Namesake collision with rename strategy
- **WHEN** a new tool collides with an existing action name and strategy is `rename`
- **THEN** runtime registers the new tool under a deterministic renamed action
- **THEN** existing action remains callable under original name
