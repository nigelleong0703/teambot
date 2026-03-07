# Agent Core Algorithm (Source of Truth)

## Purpose

This document is the canonical algorithm spec for TeamBot runtime behavior.
Any change to routing, loop termination, tool execution, reasoner prompt/payload contract, or streaming behavior must update this document in the same change.

## Scope

- Runtime loop: `reason -> act -> observe -> (loop | compose_reply)`
- Reason-stage reasoner contract (native tool call or final text)
- Tool and event-handler execution with policy gate
- Runtime event emission for transcript-style clients
- Built-in tool surface registration with profile + namesake strategy + MCP bridge
- Active skill-doc context injection for reasoner
- Streaming behavior in provider client
- Known design problems

## End-to-End Flow

```mermaid
flowchart TD
    A["Ingress (HTTP/CLI)"] --> B["AgentService.process_event"]
    B --> C{"event_id already processed?"}
    C -- "yes" --> C1["return cached reply"]
    C -- "no" --> D["build_initial_state"]
    D --> E["TeamBotRuntime.invoke"]

    subgraph L["ReAct Loop"]
      E --> F["reason_node"]
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
    R1 -- "no" --> R2{"deterministic route? (reaction, /todo, tools question)"}
    R2 -- "yes" --> R2A["select deterministic event_handler action or finish directly"]
    R2 -- "no" --> R3{"reasoner available?"}
    R3 -- "yes" --> R4["invoke reasoner with native tools"]
    R4 --> R5{"tool_calls?"}
    R5 -- "yes" --> R5B["selected_action + action_input(from tool args)"]
    R5 -- "no" --> R5A["react_done=true, action_output.message=final text"]
    R3 -- "no" --> R6["react_done=true, deterministic fallback"]
```

## Stage-by-Stage Contract

### 1) Build Initial State

- File: `src/teambot/agent/state.py`
- Initializes:
  - `react_step=0`
  - `react_max_steps=3` (default)
  - `react_done=false`
  - `selected_action=""`
  - `action_input={}`
  - `action_output={}`
  - compatibility aliases:
    - `selected_skill=""`
    - `skill_input={}`
    - `skill_output={}`

### 2) Reason (Reasoner + Deterministic Guards)

- File: `src/teambot/agent/reason.py`
- Responsibilities:
  - deterministic routes for event handlers (`reaction_added`, `/todo`) and tools question
  - reasoner call for native model tool-calling or direct final text

#### 2.1 Reasoner Prompt Source

Base system prompt is composed from working-directory markdown files in this order:

1. `AGENTS.md` (required)
2. `SOUL.md` (optional)
3. `PROFILE.md` (optional)

Then runtime appends:
- reasoner guidance text
- active skill context summary (if available)

#### 2.2 Reasoner Input/Output Contract

Reasoner payload includes:
- `event_type`, `user_text`, `reaction`, `last_observation`
- `active_skill_docs` bounded excerpts (if active skill docs exist)

Reasoner tool schema includes `tool` actions only.
Deterministic `event_handler` actions are excluded from model tool schema.
Skill docs are guidance context only; they are not executable model-callable actions.

Reasoner output is:
- native `tool_calls` -> `selected_action` + `action_input`
- or final text -> `action_output.message`

Invalid/empty reasoner output falls back safely to deterministic final reply.

### 3) Act (Unified Action + Policy Gate)

- Files:
  - `src/teambot/agent/execution.py`
  - `src/teambot/actions/registry.py`
  - `src/teambot/agent/orchestrator.py`
  - `src/teambot/agent/runtime.py`

Behavior:
- `ExecutionPolicyGate` evaluates action risk first.
- If denied (`high` risk not allowed), returns blocked result without invoking handler.
- `RuntimeOrchestrator` only builds registries/tool config/MCP wiring.
- `TeamBotRuntime.reload_runtime()` constructs `PluginHost`, the single unified action surface.
- If allowed, the selected action is invoked through that `PluginHost`.

### 3.1 Action Sources

- `tool`: external-operation tools + optional MCP bridged tools
- `event_handler`: deterministic handlers (`create_task`, `handle_reaction`)

### 3.2 Built-in Tool Profiles

- `minimal`: no tools
- `external_operation`: `read_file`, `write_file`, `edit_file`, `execute_shell_command`, `browser_use`, `get_current_time`
- `full`: external_operation + `desktop_screenshot` + `send_file_to_user`

### 3.3 High-Risk Tools (Policy-Gated)

- `write_file`
- `edit_file`
- `execute_shell_command`
- `exec_command` (alias)

### 3.4 Skills Runtime Semantics

- Active skills are managed in `active_skills` lifecycle.
- Active skill docs are injected into reasoner context for richer decision quality.
- Active skill docs are not registered as executable actions.

### 4) Observe

- File: `src/teambot/agent/execution.py`
- Updates:
  - `react_step += 1`
  - `react_done = (step >= max_steps)`
  - append `react_notes`
  - append structured `execution_trace` including action name, action input, blocked flag, and observation
  - control returns to the next `reason` step with `last_observation`

### 5) Compose Reply

- File: `src/teambot/agent/execution.py`
- `reply_text = action_output.message` else `"Processed."`
- legacy alias `skill_output.message` is still read for compatibility

### 5.1 Outbound Reply Surface

- File: `src/teambot/agent/service.py`
- `OutboundReply` now carries:
  - `text`
  - `skill_name`
  - `reasoning_note`
  - `execution_trace`
- This keeps the runtime loop deterministic while allowing presentation layers such as the CLI to render transcript-style output without re-reading internal state.

## Runtime Event Stream

- Files:
  - `src/teambot/domain/models.py`
  - `src/teambot/agent/graph.py`
  - `src/teambot/agent/reason.py`
  - `src/teambot/agent/execution.py`
  - `src/teambot/agent/service.py`
- `RuntimeEvent` is the canonical transcript event contract for step-by-step UI clients.
- The agent loop can emit:
  - `thinking_delta`
  - `tool_call`
  - `tool_result`
  - `final_delta`
  - `final_text`
  - `run_completed`
- `AgentService.stream_event(...)` runs the same core runtime path, yields `RuntimeEvent` items, persists the final reply, and keeps `process_event(...)` compatibility intact.
- `AgentService.stream_event(...)` also wraps provider token callbacks into runtime-level transcript deltas:
  - `model_reasoning_token` -> `thinking_delta`
  - `model_token` -> `final_delta`
- CLI and TUI now consume the same unified event stream instead of stitching provider callbacks separately.

## `react_done` Semantics

`react_done` is the stop flag:
- after `reason`: done -> compose, else -> act
- after `observe`: done -> compose, else -> next reason step

A loop guard (`react_max_steps + 2`) in `AgentCoreRuntime.invoke` still force-finalizes unexpected loops.

## LangChain Usage

LangChain is used in provider adapters, not in runtime control-flow:
- `src/teambot/providers/clients/langchain.py`

Runtime call chain:
- reason -> `ProviderManager.invoke_role_tools(...)` -> `LangChainProviderClient.bind_tools(...)`

## Streaming Behavior

- Files:
  - `src/teambot/providers/manager.py`
  - `src/teambot/providers/clients/langchain.py`
- If token callbacks exist, the provider client tries `model.stream(...)` for both plain-text and tool-bound turns.
- Streamed chunks are normalized back into the same `text + tool_calls` response shape used by non-streaming invocations.
- If streaming fails or yields neither text nor tool calls, the client falls back to `model.invoke(...)`.

## CLI Presentation

- File: `src/teambot/app/cli.py`
- The CLI uses a single transcript presentation driven primarily by `AgentService.stream_event(...)`.
- CLI slash commands are routed through the shared dispatcher in `src/teambot/app/slash_commands.py`.
- Runtime events are rendered as step blocks such as `Step 1 · Thinking`, `Step 1 · Tool`, `Step 1 · Result`, and `Step 2 · Final`.
- `debug on|off` controls whether raw prompt/payload and reasoning-token details are shown.
- `stream on|off` controls whether provider token streaming is rendered live.
- When provider reasoning tokens are available, the CLI appends them live inside the `Thinking` section.
- When provider text tokens are available, the CLI appends them live inside a `Final (live)` section.
- When the last streamed model text matches the final reply, the CLI suppresses duplicate final printing and marks the `Final` section as already streamed live.
- The CLI does not own runtime state transitions. It renders `OutboundReply.reasoning_note` and `OutboundReply.execution_trace` plus optional provider streaming/debug callbacks.

## TUI Presentation

- File: `src/teambot/app/tui.py`
- The TUI consumes the same `AgentService.stream_event(...)` contract as the CLI.
- TUI slash commands also use `src/teambot/app/slash_commands.py`, so supported commands are defined in one place.
- The TUI renders a Claude Code style single-column workbench instead of explicit debug sections.
- Top chrome is intentionally minimal: workspace path + `TeamBot`, with `working` only while a run is active.
- Empty state uses a compact welcome panel with workspace/model context and quick-start tips, and disables transcript scrolling until the first run starts.
- Active runs are rendered as:
  - user prompt line (`> task`)
  - subdued activity summaries (`used ...`, `observed ...`)
  - prominent final answer line
- Composer uses a single-line Claude-like prompt row with a leading `>` glyph instead of a boxed terminal input.
- `final_delta` incrementally updates the visible final answer line.
- `thinking_delta` remains available at the runtime-event layer for internal or debug-capable clients, but the TUI does not render it by default.
- Supported slash commands in the TUI:
  - `/help`
  - `/skills`
  - `/skills sync [--force]`
  - `/skills enable <name>`
  - `/skills disable <name>`
  - `/newthread`
  - `/stream on|off`
  - `/reaction <name>`
  - `/exit`
- `/tools` is intentionally not part of the user-facing slash surface in either CLI or TUI.

## Known Design Problems (Current)

1. Conversation history is stored but not injected into reasoner payload.
2. Reasoner output quality depends on provider/model behavior and prompt discipline.
3. Browser automation is still not aligned to the OpenClaw-style `browser(action=...)` protocol.
4. Streaming smoothness depends on provider chunk granularity.

## Maintenance Checklist

Update this document whenever any of these change:

- `src/teambot/agent/graph.py`
- `src/teambot/agent/reason.py`
- `src/teambot/agent/execution.py`
- `src/teambot/agent/state.py`
- `src/teambot/agent/service.py`
- `src/teambot/agent/runtime.py`
- `src/teambot/agent/orchestrator.py`
- `src/teambot/actions/registry.py`
- `src/teambot/actions/event_handlers/registry.py`
- `src/teambot/actions/event_handlers/builtin.py`
- `src/teambot/skills/context.py`
- `src/teambot/skills/manager.py`
- `src/teambot/actions/tools/runtime_builder.py`
- `src/teambot/actions/tools/external_operation_tools.py`
- `src/teambot/mcp/manager.py`
- `src/teambot/agent/prompts/system_prompt.py`
- `src/teambot/providers/manager.py`
- `src/teambot/providers/clients/langchain.py`
