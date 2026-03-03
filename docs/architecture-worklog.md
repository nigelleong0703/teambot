# Architecture Worklog

## 1. Purpose

This document is the single working log for architecture decisions.
Every discussion should update this file with:

- Decision made
- Why
- Tradeoffs
- Next action

## 2. Current Direction (Draft)

### 2.1 Orchestration Layer

- Primary: **Custom Agent Core Loop**
- Secondary helper: **LangChain adapters (required for model/tool providers)**

Why:

- We need explicit state transitions, tool gating, and fallback control in our own code.
- LangChain is used as infrastructure adapters, not as the orchestration runtime.

### 2.2 Agent Pattern

- ReAct-style loop as core runtime:
  - `reason -> act -> observe -> loop/finish`

### 2.3 Skills Lifecycle

- CoPaw-style lifecycle:
  - `builtin`
  - `customized`
  - `active` (runtime source of truth)

### 2.4 Model Strategy

- Router-first cost control:
  - lightweight router for known skill routing
  - escalate to stronger reasoning planner only for complex/open tasks
- Multi-provider is required:
  - router model and reasoning model must be independently configurable
  - provider failover and role-based model binding are mandatory

### 2.5 Tool Strategy

- Phase-based rollout:
  - start with controlled subset
  - add policy gate before high-risk tools

### 2.6 MCP Scope

- **Required in full-parity roadmap**
- Implement after tool policy/audit baseline is stable

## 3. Decision Log

| Date | Decision | Status | Notes |
|---|---|---|---|
| 2026-03-03 | Use LangGraph as core orchestration layer | Replaced | Superseded by 2026-03-03 Agent Core loop decision |
| 2026-03-03 | Use custom Agent Core loop as orchestration runtime | Accepted | LangGraph removed from primary runtime path |
| 2026-03-03 | Adopt CoPaw-style skills lifecycle | In progress | `builtin/customized/active` mechanism implemented in MVP |
| 2026-03-03 | MCP is mandatory for full-parity target | Accepted | Sequence after tool policy and audit controls |
| 2026-03-03 | Use dual-model decision architecture | Accepted | Router model + reasoning model with clear escalation boundary |
| 2026-03-03 | Multi-provider model management is mandatory | Accepted | Role-based model binding and provider failover required |

## 4. Open Questions

1. Router implementation: rules first, or lightweight model first?
2. First production tool subset: exact list and risk levels?
3. Policy gate spec: path scope, command denylist, timeout limits?
4. Skill metadata contract: which frontmatter keys are mandatory?
5. Observability baseline: what metrics are required for go-live?
6. MCP allowlist model: per server, per tool, or both?
7. Provider failover policy: immediate switch, retry budget, or hybrid?

## 5. Next Discussion Agenda

1. Freeze V1 router behavior.
2. Freeze V1 tool subset and policy gate rules.
3. Define channels/cron/memory-compaction integration contract.
4. Define MCP bridge integration and gating contract.
5. Define provider manager contract and dual-model configuration schema.

## 6. Change Protocol

When we decide something:

1. Update `Decision Log`.
2. Move related item from `Open Questions` to accepted scope.
3. Add implementation task in `Next Discussion Agenda` or execution backlog.

## 7. Proposed Code Architecture (Draft)

### 7.1 Layered Architecture

1. Ingress Layer: receives events/HTTP requests, validates payloads, and applies idempotency checks.
2. Orchestration Layer: `AgentService + AgentCoreRuntime` controls workflow transitions and fallback paths.
3. Cognition Layer: `Router + Planner` handles skill routing and complex reasoning decisions.
4. Skill Layer: `builtin/customized/active` lifecycle manages strategy and task-level behavior.
5. Tool Layer: tool registry + execution + policy gate for safety and governance.
6. State Layer: conversation history, idempotency records, memory manager, and compaction.
7. Runtime Ops Layer: channels, cron, config watcher, MCP manager, and audit logging.

### 7.2 Suggested Code Layout

1. `src/teambot/app/`: API endpoints, channel adapters, cron jobs, config watchers.
2. `src/teambot/agents/core/`: service, graph, executor, shared state contracts.
3. `src/teambot/agents/cognition/`: router, planner, prompt/context builders.
4. `src/teambot/agents/skills/`: registry, manager, packs, customized, active.
5. `src/teambot/agents/tools/`: registry, policies, adapters, builtin tools.
6. `src/teambot/state/`: store, memory manager, compaction, repositories.
7. `src/teambot/runtime/`: runner, channel manager, MCP manager.

### 7.3 Core Interfaces to Freeze

1. `Router.route(state) -> RouteDecision`
2. `Planner.plan(state, skills, policies) -> PlanResult`
3. `Skill.execute(state, skill_input) -> SkillOutput`
4. `ToolRegistry.call(tool_name, args, context) -> ToolResult`
5. `PolicyGate.authorize(tool_name, args, context) -> Allow|Deny(reason)`
6. `MemoryManager.compact(conversation_key) -> Summary`

### 7.4 Execution Path (Single Event)

1. API ingress -> idempotency check.
2. Build `AgentState` -> run router.
3. Simple requests stay on known skill route; complex/open tasks escalate to planner.
4. Agent Core loop runs `reason -> act -> observe`.
5. Every skill/tool execution passes through policy gate before action.
6. Final reply persisted with conversation turn and processed-event record.

### 7.5 Skill vs Tool Boundary

1. Skills define strategy and task-level instructions (`SKILL.md`, scripts, references).
2. Tools provide executable capabilities (`read/edit/exec/browser/mcp`).
3. Skills never bypass policy gate; all execution goes through tool framework.

### 7.6 Incremental Delivery Plan

1. M1: freeze interfaces + implement tool registry and policy gate baseline.
2. M2: stabilize router/planner split + integrate channels/cron baseline.
3. M3: add memory manager + compaction + stronger observability/audit.
4. M4: complete MCP bridge with server/tool allowlist and CLI ops workflow.
