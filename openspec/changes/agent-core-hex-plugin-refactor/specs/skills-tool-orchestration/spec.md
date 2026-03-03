## MODIFIED Requirements

### Requirement: Skills Lifecycle SHALL Be Managed Separately From Tool Execution
The system SHALL manage skill discovery and activation independently from low-level tool execution adapters, and both SHALL participate in a unified plugin lifecycle managed by a plugin host/registry layer.

#### Scenario: Skill activation refresh
- **WHEN** active skills are reloaded
- **THEN** skill availability updates without rebuilding tool adapter implementations
- **THEN** runtime sees updated skill manifests on next request

#### Scenario: Plugin lifecycle ownership
- **WHEN** a tool or skill plugin is registered or activated
- **THEN** plugin host lifecycle modules record and expose plugin state
- **THEN** runtime consumes plugin metadata through registry contracts instead of ad-hoc module globals

### Requirement: Runtime SHALL Use Unified Action Contract
The runtime SHALL resolve both registered skills and tool-backed actions through one normalized action selection contract backed by the plugin registry.

#### Scenario: Planned action resolution
- **WHEN** planner selects an action name
- **THEN** runtime resolves it against active action registry (skills and tool-backed actions)
- **THEN** runtime executes with consistent input/output envelope
