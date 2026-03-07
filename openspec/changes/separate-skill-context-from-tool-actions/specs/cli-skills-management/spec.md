## ADDED Requirements

### Requirement: CLI SHALL Provide Interactive Skills Lifecycle Commands
The CLI runtime SHALL provide interactive commands for operators to inspect and manage skills without requiring HTTP endpoints.

#### Scenario: List skills from CLI
- **WHEN** operator enters `/skills`
- **THEN** CLI prints active skill names and available skill catalog metadata
- **THEN** output indicates whether each skill is enabled

#### Scenario: Sync skills from CLI
- **WHEN** operator enters `/skills sync`
- **THEN** CLI triggers skill sync using existing lifecycle service
- **THEN** CLI reports synced/skipped counts and refreshes runtime handles

#### Scenario: Enable skill from CLI
- **WHEN** operator enters `/skills enable <name>`
- **THEN** CLI enables that skill through skill lifecycle service
- **THEN** CLI reloads runtime so the updated active set applies to subsequent requests

#### Scenario: Disable skill from CLI
- **WHEN** operator enters `/skills disable <name>`
- **THEN** CLI disables that skill through skill lifecycle service
- **THEN** CLI reloads runtime so the updated active set applies to subsequent requests
