## MODIFIED Requirements

### Requirement: Model Access SHALL Use LangChain Adapters
The system SHALL call reasoning/router/agent models through a provider-agnostic LangChain adapter interface, and concrete LangChain/provider implementations SHALL be isolated to adapter modules behind core ports.

#### Scenario: Router model invocation
- **WHEN** the runtime asks for routing or planning output
- **THEN** the call is made through a LangChain-backed adapter
- **THEN** the adapter resolves the configured provider and model name at runtime

#### Scenario: Core adapter isolation
- **WHEN** core runtime modules are executed
- **THEN** they invoke model capabilities through provider ports/contracts
- **THEN** core modules do not import provider SDK wrappers directly

### Requirement: Adapter Layer SHALL Support Multiple Providers
The system SHALL support at least two provider configurations without changing Agent Core orchestration code, and provider selection SHALL remain configuration-driven per model role.

#### Scenario: Provider switch by configuration
- **WHEN** deployment configuration changes provider settings
- **THEN** model calls continue through the same adapter contract
- **THEN** no Agent Core control-flow code change is required
