## ADDED Requirements

### Requirement: Runtime SHALL Register CoPaw-Aligned Built-In Open Tools
TeamBot runtime SHALL provide a built-in open-tools subset aligned to CoPaw baseline, including `read_file`, `write_file`, `edit_file`, `execute_shell_command`, `browser_use`, and `get_current_time`, while preserving `message_reply` as default conversational action.

#### Scenario: Baseline tools enabled
- **WHEN** runtime builds the built-in tool registry with baseline tools enabled
- **THEN** registry contains all required CoPaw-aligned tool names
- **THEN** each tool is invokable through the same action execution path as existing built-in actions

### Requirement: Built-In Tool Responses SHALL Use a Normalized Output Envelope
All built-in open-tool handlers SHALL return deterministic dict-shaped outputs with a user-facing `message` field and optional structured fields (`blocked`, `error`, or tool metadata) instead of raising uncaught exceptions into runtime flow.

#### Scenario: Tool success response
- **WHEN** a built-in open tool executes successfully
- **THEN** runtime receives a dict result containing `message`
- **THEN** `observe` and `compose_reply` can consume the output without tool-specific branching

#### Scenario: Tool failure response
- **WHEN** a built-in open tool encounters invalid input or runtime errors
- **THEN** the handler returns a safe deterministic error message in the normalized envelope
- **THEN** runtime continues without process crash

### Requirement: High-Risk Built-In Open Tools SHALL Be Classified for Policy Gate
`execute_shell_command`, `write_file`, and `edit_file` SHALL be registered as high-risk actions so that execution is subject to policy gating before handler invocation.

#### Scenario: High-risk classification
- **WHEN** built-in tools are registered
- **THEN** manifests for shell and mutating file tools declare high-risk level
- **THEN** execution policy gate evaluates them before runtime invokes handlers

### Requirement: Tool Exposure SHALL Be Environment-Configurable
Runtime SHALL support environment-driven enablement of built-in open tools for staged rollout, with defaults documented in `.env.template`.

#### Scenario: Open tools disabled by environment
- **WHEN** environment toggles disable a built-in open tool
- **THEN** that tool is not registered in active tool registry
- **THEN** runtime fallback behavior remains available via `message_reply`
