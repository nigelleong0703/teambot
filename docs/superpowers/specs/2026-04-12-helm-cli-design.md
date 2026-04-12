# Helm CLI Design

**Date:** 2026-04-12  
**Status:** Approved

## Overview

Replace the existing plain `cli.py` with a hermes-style terminal UI using `prompt_toolkit` (fixed input bar) and `rich` (colored output panels). Project is renamed **Helm** — Harness Engineering Agent Framework.

## Architecture

- `cli.py` (root) — standalone entry point, no install required (`python cli.py`)
- Internally delegates to `TeamBotCli` in `src/teambot/app/cli.py` for all agent logic
- New rendering layer wraps the existing `RuntimeEvent` stream with `rich` output and `prompt_toolkit` TUI

## Components

### Banner
Displayed on startup. Blue color scheme (`#4FC3F7` primary, `#0288D1` border).

```
╔══════════════════════════════════════════════════════╗
║  ⚙ HELM  —  Harness Engineering Agent Framework     ║
║  v0.1.0  ·  python cli.py to start                  ║
╚══════════════════════════════════════════════════════╝
```

### TUI Layout (prompt_toolkit)
- Output area: scrolling, fills terminal above input bar
- Fixed input bar at bottom with `❯` prompt and command history (stored in `~/.helm_history`)
- Spinner animation while agent is processing (`⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏`)

### Color Scheme (rich markup)

| Section   | Color            | Style   |
|-----------|------------------|---------|
| Thinking  | `#90CAF9`        | dim     |
| Tool call | `#FFB74D`        | normal  |
| Result    | `#81C784`        | normal  |
| Final     | `#4FC3F7`        | bold    |
| Error     | `red`            | bold    |
| Memory    | `#CE93D8`        | dim     |

### Input Handling
- Up/down arrow for history
- `/new` — new thread
- `/stream` — toggle token streaming
- `/debug` — toggle model payload debug
- `/exit` or Ctrl-C — quit
- `/reaction <name>` — send reaction event

## Data Flow

```
user input (prompt_toolkit)
    → build InboundEvent
    → service.stream_event()
    → RuntimeEvent stream
    → rich-colored output via ChatConsole
    → prompt_toolkit patch_stdout
```

## Dependencies

Already in `requirements.txt`:
- `prompt_toolkit>=3.0.52`
- `rich` (add to requirements.txt — currently missing)

## Files Changed

- `cli.py` — rewrite (root entry point)
- `requirements.txt` — add `rich>=13.0.0`

## Not In Scope

- Textual or other TUI frameworks
- Changing agent logic in `src/teambot/`
- Multi-pane layout
