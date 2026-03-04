## Why

Current runtime behavior is harder than necessary:

- A separate model-driven planning module returns JSON (`done`, `selected_skill`, etc.) before any action execution.
- Conflicts like `done=true` plus `selected_skill=general_reply` cause surprising short-circuit behavior.
- The model is forced to reason about planner internals instead of simply producing user-facing replies when needed.

This creates avoidable complexity for debugging and control.

## What Changes

- Remove planning-module dependency from Agent Core runtime routing (`reason` stage).
- Make `reason` stage deterministic and rule-based over unified action registry.
- Keep `general_reply` as a tool and use it as the default message action.
- Move model usage to tool execution layer (`general_reply` tool), not planner layer.
- Preserve policy-gate behavior and existing ReAct loop structure (`reason -> act -> observe -> compose_reply`).

## Capabilities

### Modified Capabilities
- `agent-core-runtime`: runtime no longer depends on planner JSON contract for core routing.
- `langchain-adapter-layer`: model invocation is used by message tool execution path instead of planning path.
- `skills-tool-orchestration`: `general_reply` is treated as a tool-backed action in unified orchestration.

## Impact

- Affected code:
  - `src/teambot/agents/core/router.py`
  - `src/teambot/agents/core/graph.py`
  - `src/teambot/agents/core/service.py`
  - `src/teambot/agents/tools/builtin.py`
  - `src/teambot/react_loop_demo.py`
- Affected tests:
  - runtime/action policy tests that currently inject planner objects.
- Affected docs:
  - `docs/agent-core-algorithm.md`
  - `repo_wiki.md`
- No new environment variables required.
