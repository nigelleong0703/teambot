# Docs Index

This directory is AI-facing and documentation-driven.

System-managed paths (do not reorganize here):
- `docs/plans/`
- `openspec/`

## Canonical Docs (read first)

1. `code-structure.md`
   - Canonical code layout and placement rules.
2. `architecture-boundaries.md`
   - Dependency boundaries and allowed direction.
3. `agent-core-algorithm.md`
   - Runtime algorithm source of truth (`reason.py`, `execution.py`, `graph.py`, skill-context injection, runtime events).

## Modules (project details)

- `modules/project-overview.md`
  - What TeamBot is, current feature set, use cases, and high-level module map.
- `modules/getting-started.md`
  - Environment setup, `.env` groups, run commands, and test commands.
  - Repo uses `requirements*.txt` plus `PYTHONPATH=src`; no editable package install path is required.
- `modules/api-and-debug.md`
  - API endpoint list and local debug utilities.
- `modules/post-change-next-steps.md`
  - Practical next-step execution plan after major runtime changes.

Current runtime terminology baseline:
- `config/`: repo-tracked runtime JSON config such as provider model definitions and profile bindings
- `agent`: the `agent/` package contains the ReAct loop, runtime owner, prompt assembly, and application service
- Canonical target structure is `agent/actions/memory/providers/skills/mcp/contracts/domain/app`
- `tools`: executable model-callable operations
- `event_handlers`: deterministic runtime handlers (e.g. reaction and `/todo`)
- `skills`: active skill packs loaded as context for the reasoner, not executable actions
- `memory`: session-scoped transcript/summary management, long-term memory loading, and reasoner context assembly
- prior conversation turns and rolling summary state are stored in `domain/store`, then assembled into reasoner context by `memory/`
- runtime conversation state is persisted under `AGENT_HOME/state/teambot.sqlite`
- provider config is layered:
  - canonical repo config via `config/config.json`, referenced by `RUNTIME_CONFIG_FILE`
  - legacy env overrides via `AGENT_*` / `SUMMARY_*` and related runtime env groups
- CLI uses a single transcript view by default:
  - `Task / Thinking / Tool / Result / Final`
  - `debug` and `stream` are visibility controls, not user-facing modes
  - when provider streaming is available, the CLI streams reasoning into `Thinking` and answer tokens into `Final (live)`
  - if the final reply text already streamed live, the `Final` section avoids printing the same answer twice
- CLI/TUI slash commands are defined centrally in `app/slash_commands.py`; `/tools` is intentionally excluded from the user-facing slash surface
- `RuntimeEvent`: domain-level event contract for step-by-step agent transcript rendering
- `AgentService.stream_event(...)`: async runtime-event stream for TUI/CLI style clients, while `process_event(...)` remains the compatibility reply API
- CLI now consumes `stream_event(...)` as its primary transcript source and renders step blocks such as `Step 1 · Thinking`, `Step 1 · Tool`, `Step 1 · Result`, `Step 2 · Final`
- TeamBot runtime now derives prompt files, skill-doc directories, and tool working paths from `AGENT_HOME`; local tool execution no longer treats process startup cwd as the primary workspace
- `RuntimeEvent` now includes live delta events:
  - `thinking_delta`
  - `final_delta`
- `app/tui.py`: terminal-native TUI entrypoint built on the same `stream_event(...)` contract and renders a Claude-like workbench without taking over terminal scrollback

## Reference Docs

- `references/copaw-baseline.md`
  - CoPaw baseline notes used for parity alignment.
- `references/claude-code-compaction-v2.1.47.md`
  - Local reverse-engineering notes for Claude Code v2.1.47 conversation compaction, including transcript boundary markers, summary generation flow, `microcompact`, and the local token estimation / autocompact threshold path.
- `references/claude-code-prompts-v2.1.47.md`
  - Local binary extraction and reconstruction of Claude Code v2.1.47 prompt templates, including main-thread, alternate, and sub-agent prompt assembly.

## Archived Docs (historical context)

- `archive/migrations/agent-core-migration.md`
- `archive/architecture/agent-runtime-architecture.md`
- `archive/architecture/framework-design.md`
- `archive/architecture/architecture-worklog.md`

## Maintenance Rules

- Any structural/runtime behavior change must update the canonical docs in the same change.
- Avoid adding loose markdown files directly under `docs/` unless they are canonical docs.
- Move outdated docs to `docs/archive/` instead of deleting them.
