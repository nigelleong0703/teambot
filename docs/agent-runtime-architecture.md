# Agent Runtime Architecture (Router / Planner / Agent Core)

## 1. Runtime Flow

```mermaid
flowchart LR
  U["User Input"] --> R["Router (rule or router_model)"]
  R -->|"direct action"| X["Executor (skill/tool)"]
  R -->|"escalate"| P["Reasoning Planner (agent_model)"]
  P --> X
  X --> O["Observe"]
  O --> C["Compose Reply"]
  C --> U2["Bot Reply"]
```

## 2. ReAct Loop (Core)

```mermaid
flowchart LR
  S["Initial State"] --> N1["reason"]
  N1 -->|"react_done=true"| N4["compose_reply"]
  N1 -->|"react_done=false"| N2["act"]
  N2 --> N3["observe"]
  N3 -->|"react_done=false"| N1
  N3 -->|"react_done=true"| N4
```

## 3. Module Mapping

- Router + loop control:
  - `src/teambot/agents/core/router.py`
  - `src/teambot/agents/core/graph.py`
- Planner (rule + model planner):
  - `src/teambot/agents/planner.py`
- Model provider manager:
  - `src/teambot/agents/providers/*`
- Skill/tool execution:
  - `src/teambot/agents/core/executor.py`
  - `src/teambot/plugins/registry.py`
- Composition root:
  - `src/teambot/interfaces/bootstrap.py`
