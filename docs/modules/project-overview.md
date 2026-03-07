# Project Overview

## What TeamBot Is

TeamBot is an agent-first backend runtime for chat automation systems.

It is not a prompt-only chatbot wrapper. It is an execution runtime that combines:
- deterministic ReAct control flow
- explicit skill/tool registration
- policy-gated action execution
- optional model-backed planning (native tool calls or direct final text)

## Current Feature Set

- ReAct runtime loop: `reason -> act -> observe -> compose_reply`
- Runtime owner: `TeamBotRuntime`
- Tool runtime profiles:
  - `minimal`
  - `external_operation`
  - `full`
- Built-in operational tools:
  - file read/write/edit
  - shell command execution
  - browser fetch
  - current time
- Skills lifecycle:
  - sync
  - enable/disable
  - active-skills runtime loading
- Optional MCP bridge into the same action surface
- Event idempotency and deterministic thread routing
- Runtime transcript event stream for CLI/TUI clients
- Textual TUI with Claude-like single-column workbench rendering

## Typical Use Cases

- Build a Slack-like team assistant backend.
- Extend capabilities through local skills and tools.
- Bridge MCP tools into runtime action execution.
- Run local deterministic + model-assisted agent flows for development.

## High-Level Module Map

- Runtime core: `src/teambot/agent/runtime.py`
- ReAct internals: `src/teambot/agent/*`
- Tools: `src/teambot/actions/tools/*`
- Skills: `src/teambot/skills/*`
- MCP: `src/teambot/mcp/*`
- Providers: `src/teambot/providers/*`
- API entry: `src/teambot/app/main.py`
- CLI entry: `src/teambot/app/cli.py`
- TUI entry: `src/teambot/app/tui.py`
