# Project Overview

## What TeamBot Is

TeamBot is an agent-first backend runtime for chat automation systems.

It is not a prompt-only chatbot wrapper. It is an execution runtime that combines:
- deterministic ReAct control flow
- explicit skill/tool registration
- policy-gated action execution
- optional model-backed message replies

## Current Feature Set

- ReAct runtime loop: `reason -> act -> observe -> compose_reply`
- Runtime owner: `TeamBotReactAgent`
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

## Typical Use Cases

- Build a Slack-like team assistant backend.
- Extend capabilities through local skills and tools.
- Bridge MCP tools into runtime action execution.
- Run local deterministic + model-assisted agent flows for development.

## High-Level Module Map

- Runtime core: `src/teambot/agents/react_agent.py`
- ReAct internals: `src/teambot/agents/core/*`
- Tools: `src/teambot/agents/tools/*`
- Skills: `src/teambot/agents/skills/*`
- MCP: `src/teambot/agents/mcp/*`
- Providers: `src/teambot/agents/providers/*`
- API entry: `src/teambot/main.py`
- CLI entry: `src/teambot/cli.py`
