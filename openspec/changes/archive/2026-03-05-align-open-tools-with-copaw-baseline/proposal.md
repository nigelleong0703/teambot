## Why

TeamBot's built-in tools are currently not aligned with the CoPaw baseline, leaving only `message_reply` active and `tool_echo` / `exec_command` as placeholders. This gap blocks practical tool-first workflows and makes planner behavior diverge from the reference runtime.

## What Changes

- Add a first-class built-in open-tools set aligned to the CoPaw baseline: `read_file`, `write_file`, `edit_file`, `execute_shell_command`, `browser_use`, `get_current_time`, with optional parity extensions (`desktop_screenshot`, `send_file_to_user`) behind explicit enable flags.
- Replace placeholder-only execution behavior with real tool handlers and normalized result envelopes compatible with current Agent Core action dispatch.
- Introduce centralized policy gates for high-risk operations (shell execution and write/edit actions), including explicit blocked responses when denied.
- Keep `message_reply` as the safe default action and retain environment-driven toggles for staged rollout.
- Add verification tests and documentation updates for tool routing, policy denials, and parity scope.

## Capabilities

### New Capabilities
- `builtin-open-tools-parity`: Defines the runtime contract for CoPaw-aligned built-in tool registration, execution, and policy-gated behavior in TeamBot.

### Modified Capabilities
- `skills-tool-orchestration`: Expands the unified action contract to require deterministic resolution and risk gating for the new built-in open-tools set.

## Impact

- Affected code: `src/teambot/agents/tools/builtin.py`, `src/teambot/agents/tools/registry.py`, tool module additions under `src/teambot/agents/tools/`, runtime orchestration path that invokes tools.
- Affected tests: tool registry and action execution tests for success, blocked, and fallback paths.
- Affected docs: `docs/agent-core-algorithm.md`, `repo_wiki.md`, and `.env.template` for new/updated tool policy flags.
