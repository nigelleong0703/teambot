## Context

The current architecture already has a custom Agent Core loop, but runtime routing still depends on a dedicated planning module that asks the model to emit structured planning JSON. That layer introduces control ambiguity (`done` versus `selected_skill`) and increases cognitive load without clear product benefit for MVP behavior.

This change simplifies the core by making routing deterministic and reserving model calls for user-facing message generation inside `general_reply` tool execution.

## Goals / Non-Goals

**Goals:**
- Keep the existing ReAct runtime loop shape.
- Remove planner dependency from runtime reason-node decisions.
- Keep unified action contract across skills and tools.
- Keep LangChain/provider usage behind adapter layer.
- Make `general_reply` the default message tool path.

**Non-Goals:**
- Removing provider manager or LangChain adapter support.
- Removing planner module files entirely in this change.
- Changing policy gate semantics.
- Introducing MCP or multi-agent planning.

## Decisions

1. **Deterministic reason stage**
   - Decision: `reason` routes actions via deterministic rule priority, not model planning JSON.
   - Priority order:
     1) step guard (`react_step >= react_max_steps`) => done
     2) `skill_output.next_skill` valid => continue that action
     3) event rule (`reaction_added -> handle_reaction`)
     4) command rule (`/todo -> create_task`)
     5) default action (`general_reply`, else first available action)
   - Rationale: removes planner ambiguity and makes routing predictable.

2. **Model usage moved to message tool**
   - Decision: `general_reply` tool can invoke provider manager (`ROLE_AGENT`) using a strict JSON response schema with `message`.
   - Rationale: model is used where it adds value (reply generation), without forcing planner abstraction.

3. **Runtime wiring no longer takes Planner dependency**
   - Decision: `AgentCoreRuntime` and `build_graph` no longer accept a planner.
   - Rationale: reduce constructor coupling and eliminate unused abstraction in core loop.

4. **Keep policy gate unchanged**
   - Decision: all action execution still passes through `ExecutionPolicyGate`.
   - Rationale: simplification should not weaken safety behavior.

## Prompt Contract (general_reply tool)

System prompt contract used by `general_reply` when model is available:

- Instruct the model to return one JSON object only.
- Expected schema: `{ "message": string }`.
- No markdown or extra wrapper text.
- Fallback to deterministic local reply when provider call fails or `message` is missing.

## Risks / Trade-offs

- [Loss of model-driven action selection flexibility] -> Mitigation: deterministic rules remain extensible and are easier to validate.
- [Provider/model errors in `general_reply`] -> Mitigation: deterministic fallback reply path.
- [Existing planner-focused tests become obsolete] -> Mitigation: replace with deterministic routing tests and tool-level model invocation tests.

## Migration Plan

1. Update OpenSpec requirements for runtime, adapter, and orchestration capabilities.
2. Refactor runtime router/graph/service to remove planner dependency.
3. Upgrade `general_reply` tool to model-backed message generation with deterministic fallback.
4. Update debug runner and tests to reflect tool-first model usage.
5. Update core algorithm and wiki docs to match new behavior.
6. Validate with `openspec validate` and test suite.

Rollback strategy:
- Reintroduce planner injection in `build_graph`/`AgentCoreRuntime` and restore planner route branch in `reason`.
- Keep tool-side model prompt as optional feature.
