# Code Structure (Canonical)

This is the single source of truth for TeamBot code layout.

## 1. Directory Layout

```text
config/               # repo-tracked runtime JSON config (canonical: config/config.json)
src/teambot/
  app/                 # entrypoints (API/CLI/bootstrap)
  gateway/             # ingress orchestration and envelope-to-agent dispatch
  agent/               # ReAct loop, runtime owner, and application service
  actions/             # executable actions: tools + deterministic event handlers
  memory/              # transcript context assembly, long-term memory, compaction
  providers/           # model/provider clients and provider manager
  skills/              # skill docs lifecycle and reasoner context assembly
  mcp/                 # MCP config, manager, and bridge
  contracts/           # cross-module protocols and thin shared interfaces
  domain/              # TeamBot business objects and persistent state shapes
  workflows/           # complex execution engine (optional path)
  channels/            # multi-channel SDK bridges and shared envelope models
```

This is the canonical current layout.
New code MUST follow the layout above.

## 2. Term Definitions

- `agent`
  - Owns the ReAct execution path.
  - Expected contents: `runtime.py`, `service.py`, `graph.py`, `reason.py`, `reasoner_context.py`, `execution.py`, `state.py`, `policy.py`.
  - This is where you change how the agent runs.

- `gateway`
  - Owns ingress orchestration between transport-facing channel runtimes and `AgentService`.
  - Expected contents: request dispatch, ingress response models, and envelope-to-agent-event mapping.
  - This is where you change how inbound HTTP events are routed into the runtime.

- `channels`
  - Owns platform SDK bridges plus the neutral ingress DTOs shared with `gateway`.
  - SDK-backed runtimes live under `channels/runtimes/`; legacy generic adapters remain only as compatibility fallbacks for non-SDK routes.

- `actions`
  - Owns executable runtime actions.
  - This is the execution surface for the system.
  - It contains:
    - `tools/`: model-callable operations such as `read_file`, `execute_shell_command`, `web_fetch`, `browser`, `get_current_time`
    - `event_handlers/`: deterministic handlers such as `/todo` and reaction processing

- `providers`
  - Owns model/provider integrations and provider selection.
  - Owns model definitions, profile bindings, and provider client routing.
  - This is where OpenAI-compatible, Anthropic, and related client wiring belongs.

- `memory`
  - Owns session-scoped memory management and long-term memory loading.
  - This is where transcript compaction, rolling summaries, session-context policy, and memory-context injection belong.

- `skills`
  - Owns skill docs lifecycle and context assembly.
  - Skills are context for the reasoner.
  - Skills are activated through request context and the `activate_skill` tool, not through executable Python plugins.

- `mcp`
  - Owns MCP configuration, client manager, and bridge code.

- `contracts`
  - Owns protocol-like definitions shared across modules.
  - Examples: tool call shapes, registry contracts, thin interfaces.
  - It must not contain runtime flow, provider SDK calls, or tool implementations.

- `domain`
  - Owns TeamBot's core objects and stored state.
  - Examples: `InboundEvent`, `OutboundReply`, `RuntimeEvent`, conversation records, store models, bounded prior-turn history passed into the reasoner state.

## 3. Dependency Direction

Allowed:
- `app -> gateway/channels/agent/actions/memory/providers/skills/mcp/domain/contracts/workflows`
- `gateway -> channels/agent/domain/contracts`
- `channels -> domain/contracts`
- `workflows -> agent/actions/memory/providers/skills/mcp/domain/contracts`
- `agent -> actions/memory/providers/skills/mcp/domain/contracts`
- `actions -> domain/contracts`
- `memory -> domain/contracts`
- `providers -> contracts`
- `skills -> domain/contracts`
- `mcp -> actions/providers/contracts`

Disallowed:
- `domain -> gateway/agent/actions/memory/providers/skills/mcp/channels/workflows`
- `agent -> gateway/channels`
- `actions -> channels`
- `channels -> agent`
- `providers -> agent`
- `contracts -> provider SDK wrappers`
- `contracts -> runtime implementations`

## 4. File Placement Rules

- Do not add new business `.py` files directly under `src/teambot/`.
- Shared DTO/state types go to `domain` (e.g. inbound/outbound/session).
- Runtime transcript/event contracts also go to `domain` (e.g. `RuntimeEvent`).
- Storage logic goes to `domain/store`.
- Runtime-local persisted state such as SQLite-backed conversation history and processed-event caches also belongs under `domain/store`.
- Session-memory management, long-term memory loading, and compaction policy belong under `memory/`.
- Ingress orchestration, request verification flow, and adapter dispatch belong under `gateway/`.
- ReAct loop logic goes to `agent/`.
- `agent/` should stay focused on `runtime.py`, `service.py`, `graph.py`, `reason.py`, `reasoner_context.py`, `execution.py`, `state.py`, and `policy.py`.
- Channel-specific request parsing and normalization belong under `channels/`.
- Final reasoner request composition belongs under `agent/`; `memory/` and `skills/` should provide bounded context inputs rather than directly owning the final request envelope.
- Executable model-callable operations belong under `actions/tools/`.
- Deterministic event-driven actions belong under `actions/event_handlers/`.
- Provider integrations belong under `providers/`.
- Skills docs/context lifecycle belongs under `skills/`.
- MCP runtime belongs under `mcp/`.
- Protocols/contracts belong under `contracts/`.
- Active skill docs should remain context-only.
- Debug/utility runners should be under `app` (or a dedicated scripts area), not package root.
- `app/cli.py` and `app/tui.py` own presentation only. Runtime trace/event generation stays in `agent/` and is surfaced via `RuntimeEvent` / `OutboundReply`.
- Shared slash-command definitions belong in `app/slash_commands.py`. CLI and TUI should consume that shared dispatcher instead of maintaining separate command lists.
- Local execution context such as startup cwd should be captured in runtime state, not rediscovered ad hoc inside tool implementations.

## 5. Documentation Rule

- Any structural change MUST update this file in the same change.
- Other docs should link here instead of redefining structure rules.
- Local development runs the repo directly from `src/` with `PYTHONPATH=src`; editable package installation is not part of the default workflow.
