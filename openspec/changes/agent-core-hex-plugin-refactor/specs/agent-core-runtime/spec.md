## MODIFIED Requirements

### Requirement: Agent Core SHALL Own Runtime Control Flow
The system SHALL execute agent requests through a custom runtime loop that does not depend on LangGraph graph compilation or graph invocation at runtime, and this runtime loop SHALL depend only on core contracts rather than adapter implementations.

#### Scenario: Runtime starts a request
- **WHEN** an inbound event is accepted by AgentService
- **THEN** the request is executed by the custom Agent Core loop entrypoint
- **THEN** no LangGraph runtime object is required to process the event

#### Scenario: Runtime resolves dependencies
- **WHEN** the runtime needs model, tool, or skill execution capabilities
- **THEN** it resolves them through core contract interfaces
- **THEN** runtime control-flow modules avoid direct imports of provider/tool SDK adapters
