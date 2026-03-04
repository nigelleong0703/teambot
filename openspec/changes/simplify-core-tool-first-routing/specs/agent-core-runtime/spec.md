## MODIFIED Requirements

### Requirement: Agent Core SHALL Own Runtime Control Flow
The system SHALL execute agent requests through a custom runtime loop that does not depend on LangGraph runtime objects or planner-module model outputs for routing decisions.

#### Scenario: Runtime starts a request
- **WHEN** an inbound event is accepted by AgentService
- **THEN** request processing runs through Agent Core loop (`reason -> act -> observe -> compose_reply`)
- **THEN** runtime routing decisions are resolved inside deterministic reason-node logic

### Requirement: Agent Core SHALL Use Deterministic Reason Routing Priority
The reason stage SHALL choose next action using deterministic priority rules.

#### Scenario: Max-step guard
- **WHEN** `react_step >= react_max_steps`
- **THEN** runtime marks execution done
- **THEN** compose_reply returns a safe fallback message if needed

#### Scenario: Follow-up action continuation
- **WHEN** previous observation includes `next_skill`
- **THEN** runtime executes that action if registered
- **THEN** runtime falls back to default action if follow-up action is unknown

#### Scenario: Event and command routing
- **WHEN** event type is `reaction_added`
- **THEN** runtime prefers `handle_reaction` when available
- **THEN** `/todo` message inputs prefer `create_task` when available

#### Scenario: Default message action
- **WHEN** no higher-priority rule applies
- **THEN** runtime selects `general_reply` if available
- **THEN** runtime may select first available action or finish safely when none exists
