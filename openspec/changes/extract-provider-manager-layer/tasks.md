## 1. Provider Manager Foundation

- [x] 1.1 Create `src/teambot/agents/providers/` package with base contracts and module skeletons
- [x] 1.2 Implement provider configuration schema and loader with env compatibility mapping
- [x] 1.3 Implement provider client registry for provider/model/endpoint instantiation
- [x] 1.4 Implement normalized response envelope for all provider outputs

## 2. Role Binding And Failover

- [x] 2.1 Implement role binding registry for `router_model` and `agent_model`
- [x] 2.2 Implement deterministic provider fallback sequence with bounded retry policy
- [x] 2.3 Add structured provider error/attempt reporting for planner fallback handling
- [x] 2.4 Add tests for role binding and failover routing behavior

## 3. Planner Integration

- [x] 3.1 Refactor planner to consume provider manager interface instead of direct endpoint parsing
- [x] 3.2 Keep compatibility shim for current model adapter entry points during migration
- [x] 3.3 Remove planner-level provider branching logic after integration parity is validated
- [x] 3.4 Add tests for router-model and agent-model invocation paths via provider manager

## 4. Validation And Documentation

- [x] 4.1 Verify end-to-end API behavior parity for message/reaction flows
- [x] 4.2 Add regression tests for structured output validation with normalized responses
- [x] 4.3 Update runtime configuration docs with provider manager role settings
- [x] 4.4 Validate OpenSpec change and confirm apply-ready status
