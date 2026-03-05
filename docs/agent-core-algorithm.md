# Agent Core Algorithm (Source of Truth)

## Purpose

This document is the canonical algorithm spec for TeamBot runtime behavior.
Any change to routing, loop termination, tool execution, model prompt contract, or streaming behavior must update this document in the same change.

## Scope

- Runtime loop: `reason -> act -> observe -> (loop | compose_reply)`
- Reason-stage planning contract (native tool call or final text)
- Tool execution and policy gate behavior
- Built-in tool surface registration with profile + namesake strategy + MCP bridge
- Model prompt contract used by planner in reason stage
- Streaming behavior in provider client
- Known design problems

## End-to-End Flow

```mermaid
flowchart TD
    A["Ingress (HTTP/CLI)"] --> B["AgentService.process_event"]
    B --> C{"event_id already processed?"}
    C -- "yes" --> C1["return cached reply"]
    C -- "no" --> D["build_initial_state"]
    D --> E["TeamBotReactAgent.invoke"]

    subgraph L["ReAct Loop"]
      E --> F["reason_node (deterministic)"]
      F --> G{"react_done?"}
      G -- "true" --> H["compose_reply_node"]
      G -- "false" --> I["act_node"]
      I --> J["observe_node"]
      J --> K{"react_done?"}
      K -- "false" --> F
      K -- "true" --> H
    end

    H --> M["build OutboundReply"]
    M --> N["append turns + save processed event"]
    N --> O["return reply"]
```

## Reason Stage Priority

```mermaid
flowchart TD
    R0["reason_node"] --> R1{"react_step >= react_max_steps?"}
    R1 -- "yes" --> R1D["react_done=true, finish"]
    R1 -- "no" --> R2{"skill_output.next_skill exists?"}
    R2 -- "yes" --> R2A["selected_skill=next_skill"]
    R2 -- "no" --> R3{"deterministic direct route? (/todo, reaction, tools question)"}
    R3 -- "yes" --> R3A["select action or finish directly"]
    R3 -- "no" --> R4{"planner available?"}
    R4 -- "yes" --> R5["invoke planner(native tools)"]
    R5 --> R6{"tool_calls?"}
    R6 -- "yes" --> R6B["selected_skill + skill_input(from tool args)"]
    R6 -- "no" --> R6A["react_done=true, skill_output.message=final text"]
    R4 -- "no" --> R7["react_done=true, deterministic fallback"]
```

## Stage-by-Stage Contract

### 1) Build Initial State

- File: `src/teambot/agents/core/state.py`
- Model prompt: none.
- Initializes:
  - `react_step=0`
  - `react_max_steps=3` (default)
  - `react_done=false`
  - `selected_skill=""`
  - `skill_input={}`
  - `skill_output={}`

### 2) Reason (Planner + Deterministic Guards)

- File: `src/teambot/agents/core/router.py`
- Model prompt: yes (when provider role is configured).
- Responsibility:
  - follow-up route (`next_skill`) from previous observation
  - deterministic direct routes (`reaction_added`, `/todo`, tools question)
  - planner result via native model tool-calling or direct final text
- Planner system prompt combines working-dir prompt + tool-usage guidance.

### 3) Act (Unified Action + Policy Gate)

- Files:
  - `src/teambot/agents/core/executor.py`
  - `src/teambot/agents/react_agent.py`
  - `src/teambot/agents/prompts/system_prompt.py`
  - `src/teambot/agents/tools/builtin.py`
  - `src/teambot/agents/tools/runtime_builder.py`
  - `src/teambot/agents/tools/catalog.py`
  - `src/teambot/agents/tools/profiles.py`
  - `src/teambot/agents/tools/namesake.py`
  - `src/teambot/agents/tools/external_operation_tools.py`
  - `src/teambot/agents/runtime/orchestrator.py`
  - `src/teambot/agents/mcp/manager.py`
  - `src/teambot/agents/mcp/bridge.py`
- Behavior:
  - `ExecutionPolicyGate` evaluates action risk first.
  - If denied (`high` risk not allowed), returns blocked result.
  - If allowed, invokes selected action through unified action registry.

#### 2.1 Planner model prompt source

Used when provider manager exists and has `agent_model` role binding.
Base system prompt is composed from working-directory markdown files in this order:

1. `AGENTS.md` (required)
2. `SOUL.md` (optional)
3. `PROFILE.md` (optional)

#### 2.2 Planner input/output contract

- Planner input payload includes:
  - `event_type`, `user_text`, `reaction`, `last_observation`
- Planner receives native tool schemas (for runtime-enabled tools).
- Planner output is one of:
  - native `tool_calls` (name + args), mapped to `selected_skill` + `skill_input`
  - plain final text, mapped to `skill_output.message`
- If planner output is empty/invalid, runtime safely falls back to final deterministic reply.

#### 3.1 Built-in tool surface profiles

- Tool set is assembled by runtime profile (`TOOLS_PROFILE`) and namesake strategy (`TOOLS_NAMESAKE_STRATEGY`).
- Supported profiles:
  - `minimal`: no tools
  - `external_operation`: `read_file`/`write_file`/`edit_file`/`execute_shell_command`/`browser_use`/`get_current_time`
  - `full`: `external_operation` + `desktop_screenshot` + `send_file_to_user`
- Optional debug toggles:
  - `ENABLE_ECHO_TOOL=true` -> `tool_echo`
  - `ENABLE_EXEC_TOOL=true` -> `exec_command` alias
- Namesake strategy controls conflict behavior for runtime-injected tools (`skip|override|raise|rename`).

#### 3.2 High-risk external-operation tools

- The following built-in tools are classified as `high` risk and policy-gated:
  - `write_file`
  - `edit_file`
  - `execute_shell_command`
  - `exec_command` (alias)
- When blocked, runtime returns deterministic blocked output without invoking the underlying handler.

#### 3.3 Skills runtime loading semantics

- Runtime loads skills from `active_skills` only.
- `ensure_skills_initialized()` does not auto-sync skills anymore; it warns when active set is empty.
- Skill enable/sync lifecycle is explicit via skill manager operations.

#### 3.4 MCP runtime injection

- MCP tools are loaded by MCP manager when `MCP_ENABLED=true`.
- MCP tool manifests are bridged into the same `ToolRegistry` and action contract as builtin tools.
- Namesake strategy also applies to MCP-vs-builtin name collisions.

### 4) Observe

- File: `src/teambot/agents/core/executor.py`
- Model prompt: none.
- Updates:
  - `react_step += 1`
  - `react_done = (not next_skill) or (step >= max_steps)`
  - appends to `react_notes`
  - appends to `execution_trace`

### 5) Compose Reply

- File: `src/teambot/agents/core/executor.py`
- Model prompt: none.
- `reply_text = skill_output.message` else `"Processed."`

## `react_done` Semantics

`react_done` is the stop flag used by router transitions:

- after `reason`:
  - `react_done=true` -> `compose_reply`
  - `react_done=false` -> continue to `act`
- after `observe`:
  - `react_done=true` -> `compose_reply`
  - `react_done=false` -> next loop iteration

A runtime loop guard (`react_max_steps + 2`) still exists in `AgentCoreRuntime.invoke` to force-safe completion if unexpected loops occur.

## LangChain Usage (Where It Is Actually Used)

LangChain is used in provider client adapters, not in runtime control-flow files:

- `src/teambot/agents/providers/clients/langchain.py`
  - `langchain_core.messages`
  - `langchain_openai.ChatOpenAI`
  - `langchain_anthropic.ChatAnthropic`

Runtime call chain for model planning:

- `reason planner` -> `ProviderManager.invoke_role_tools(...)` -> `LangChainProviderClient.bind_tools(...)`

## Streaming Behavior

- Files:
  - `src/teambot/agents/providers/manager.py`
  - `src/teambot/agents/providers/clients/langchain.py`
- If token callbacks are present, provider client attempts `model.stream(...)`.
- If stream fails or yields no chunks, client falls back to `model.invoke(...)`.
- Therefore visible UX can look like pseudo-streaming when upstream providers emit coarse chunks.

## Known Design Problems (Current)

1. Conversation history is stored but not injected into planner payload.
2. Planner output quality depends on provider/model behavior and prompt discipline.
3. `observe` marks done when `next_skill` is absent, which biases toward single-step completion.
4. Streaming smoothness still depends on provider chunk granularity.

## Maintenance Checklist

Update this document whenever any of the following changes:

- `src/teambot/agents/core/router.py`
- `src/teambot/agents/core/graph.py`
- `src/teambot/agents/core/executor.py`
- `src/teambot/agents/tools/builtin.py`
 - `src/teambot/agents/tools/runtime_builder.py`
 - `src/teambot/agents/tools/catalog.py`
 - `src/teambot/agents/tools/profiles.py`
 - `src/teambot/agents/tools/namesake.py`
- `src/teambot/agents/tools/external_operation_tools.py`
 - `src/teambot/agents/runtime/orchestrator.py`
 - `src/teambot/agents/mcp/manager.py`
 - `src/teambot/agents/mcp/bridge.py`
 - `src/teambot/agents/skills/runtime_loader.py`
 - `src/teambot/agents/skills/manager.py`
- `src/teambot/agents/prompts/system_prompt.py`
- `src/teambot/agents/providers/manager.py`
- `src/teambot/agents/providers/clients/langchain.py`
- `src/teambot/agents/core/state.py`
- `src/teambot/agents/core/service.py`
- `src/teambot/agents/react_agent.py`

