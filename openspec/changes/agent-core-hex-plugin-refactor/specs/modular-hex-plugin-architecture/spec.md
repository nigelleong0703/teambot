## ADDED Requirements

### Requirement: Backend SHALL Follow Modular Monolith Boundaries
The system SHALL organize backend code into explicit architecture modules with clear ownership boundaries, including core runtime modules, adapter implementations, plugin lifecycle modules, and interface entrypoints.

#### Scenario: Add new backend feature
- **WHEN** a new backend feature is implemented
- **THEN** its runtime business logic is placed in core modules
- **THEN** external SDK and transport logic is placed in adapters or interfaces, not in core modules

### Requirement: Core Modules SHALL Depend on Ports, Not Adapter Implementations
Core runtime and planning modules SHALL depend only on declared contracts/ports for model, tool, and plugin interactions.

#### Scenario: Core invokes model provider
- **WHEN** planner/runtime requests model execution
- **THEN** the request is issued through a core contract interface
- **THEN** no core import references provider-specific adapter modules directly

### Requirement: System SHALL Provide a Single Composition Root
The system SHALL initialize runtime dependencies from a single bootstrap composition root that is reused by API and CLI interfaces.

#### Scenario: API and CLI startup
- **WHEN** API and CLI processes initialize the agent runtime
- **THEN** both startup paths call the same composition root for provider and plugin wiring
- **THEN** runtime behavior remains consistent across interfaces
