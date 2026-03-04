## MODIFIED Requirements

### Requirement: Model Access SHALL Use LangChain Adapters
The system SHALL call LLM providers through the provider-agnostic LangChain adapter interface, and runtime core modules SHALL consume this through adapter contracts.

#### Scenario: Message tool invocation
- **WHEN** `general_reply` requires model-generated text
- **THEN** it invokes provider manager through adapter-layer contracts
- **THEN** provider/model selection remains configuration-driven

### Requirement: Adapter Layer SHALL Support Multiple Providers
The system SHALL support switching provider backends by configuration without changing Agent Core runtime flow code.

#### Scenario: Provider switch by configuration
- **WHEN** deployment changes role binding endpoint/provider/model
- **THEN** `general_reply` model invocation still uses the same adapter contract
- **THEN** no runtime loop control-flow refactor is required

### Requirement: Structured Model Output SHALL Be Validated At Tool Boundary
The adapter-integrated message tool SHALL validate structured model output before composing user-visible reply text.

#### Scenario: Invalid model payload
- **WHEN** model output does not include valid `message` string field
- **THEN** tool falls back to deterministic local message
- **THEN** runtime continues without crashing
