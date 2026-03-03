## ADDED Requirements

### Requirement: Provider Manager SHALL Own Provider Configuration and Client Registry
The system SHALL manage model provider configuration and provider client instances through a dedicated provider manager layer, not inside planner or runtime loop modules.

#### Scenario: Load provider settings
- **WHEN** runtime initializes model dependencies
- **THEN** provider manager loads provider configs and builds provider clients
- **THEN** planner/runtime consume provider manager interfaces instead of raw endpoint parsing

### Requirement: Provider Manager SHALL Support Role-Based Model Binding
The system SHALL support explicit model-role binding for at least `router_model` and `agent_model`, each independently mapped to provider/model/endpoint settings.

#### Scenario: Resolve agent role binding
- **WHEN** planner requests `agent_model` execution
- **THEN** provider manager resolves the configured provider and model for the `agent_model` role
- **THEN** planner receives a callable model client without endpoint-specific branching

### Requirement: Provider Manager SHALL Provide Deterministic Provider Failover
The system SHALL support deterministic failover across configured providers for a role, with bounded retry behavior and explicit failure reporting.

#### Scenario: Primary provider fails
- **WHEN** the first provider for `router_model` returns transport/provider error
- **THEN** provider manager retries using the next configured provider for the same role
- **THEN** if all candidates fail, planner receives a structured provider failure error for fallback logic

### Requirement: Provider Manager SHALL Normalize Model Responses
The system SHALL normalize provider-specific response payloads into a consistent structure containing at least content text, finish reason, and usage metadata (when available).

#### Scenario: Anthropic/OpenAI-compatible response normalization
- **WHEN** different providers return different raw response schemas
- **THEN** provider manager returns a normalized response object with stable fields
- **THEN** planner validation logic consumes the normalized shape without provider-specific parsing branches
