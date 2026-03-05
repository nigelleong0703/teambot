# skills-tool-orchestration Specification

## Purpose
TBD - created by archiving change migrate-all-to-langchain. Update Purpose after archive.
## Requirements
### Requirement: Skills Lifecycle SHALL Be Managed Separately From Tool Execution
The system SHALL manage skill discovery/activation independently from low-level tool execution adapters.

#### Scenario: Skill activation refresh
- **WHEN** active skills are reloaded
- **THEN** skill availability updates without rebuilding tool adapter implementations
- **THEN** runtime sees updated skill manifests on next request

#### Scenario: Active-only runtime loading
- **WHEN** runtime builds skill registry
- **THEN** it loads only skills present in `active_skills`
- **THEN** empty active set does not implicitly sync skills from builtin/customized directories

### Requirement: Runtime SHALL Use Unified Action Contract
The runtime SHALL resolve both registered skills and built-in external-operation tools through one normalized action selection contract, including CoPaw-aligned tool names and deterministic fallback behavior.

#### Scenario: Planned action resolution for built-in external-operation tool
- **WHEN** planner or deterministic router selects a registered built-in external-operation tool action
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

### Requirement: MCP Tools SHALL Integrate Into Unified Action Surface
When MCP runtime is enabled, MCP tools SHALL be bridged into the same action registry and execution envelope as builtin tools and skills.

#### Scenario: MCP tool registration
- **WHEN** MCP manager initializes enabled servers with tools
- **THEN** MCP tool manifests are registered into active tool registry
- **THEN** those actions are invokable through the same unified action contract
