# langchain-adapter-layer Specification

## Purpose
TBD - created by archiving change migrate-all-to-langchain. Update Purpose after archive.
## Requirements
### Requirement: Model Access SHALL Use LangChain Adapters
The system SHALL call reasoning/router/agent models through a provider-agnostic LangChain adapter interface.

#### Scenario: Router model invocation
- **WHEN** the runtime asks for routing or planning output
- **THEN** the call is made through a LangChain-backed adapter
- **THEN** the adapter resolves the configured provider and model name at runtime

### Requirement: Adapter Layer SHALL Support Multiple Providers
The system SHALL support at least two provider configurations without changing Agent Core orchestration code.

#### Scenario: Provider switch by configuration
- **WHEN** deployment configuration changes provider settings
- **THEN** model calls continue through the same adapter contract
- **THEN** no Agent Core control-flow code change is required

### Requirement: Structured Planner Output SHALL Be Validated
The adapter layer SHALL parse and validate structured planner outputs before they reach runtime routing decisions.

#### Scenario: Invalid structured response
- **WHEN** model output misses required planning fields or references unknown action names
- **THEN** validation fails fast
- **THEN** runtime falls back to deterministic planner policy

