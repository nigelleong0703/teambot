## MODIFIED Requirements

### Requirement: Skills Lifecycle SHALL Be Managed Separately From Tool Execution
The system SHALL manage skill discovery/activation as reasoning-context resources independently from executable tool adapters.

#### Scenario: Skill activation refresh
- **WHEN** active skills are reloaded
- **THEN** skill availability updates without rebuilding tool adapter implementations
- **THEN** runtime reasoner context uses the updated active skill docs on next request

#### Scenario: Active-only runtime loading
- **WHEN** runtime builds skill context index
- **THEN** it loads only skills present in `active_skills`
- **THEN** empty active set does not implicitly sync skills from builtin/customized directories

### Requirement: Runtime SHALL Use Unified Action Contract
The runtime SHALL resolve executable actions through one normalized action contract where model-selected execution targets are tool actions, while deterministic event handlers are resolved by router precedence outside model tool-calling.

#### Scenario: Planned action resolution for built-in external-operation tool
- **WHEN** reasoner selects a registered built-in external-operation tool action
- **THEN** runtime resolves it against the active action registry without a separate code path
- **THEN** runtime executes it with the normalized input/output envelope

#### Scenario: Deterministic event handler resolution
- **WHEN** inbound event matches deterministic event-handler rules (for example reaction or `/todo`)
- **THEN** runtime resolves and executes handler behavior without exposing it as model tool-call candidate
- **THEN** runtime records execution trace in the same normalized envelope

#### Scenario: Selected action not available
- **WHEN** selected action is absent from active action registry
- **THEN** runtime falls back to default action resolution rules
- **THEN** runtime does not terminate with unresolved-action failure
