## 1. Built-In Open Tools Parity Wiring

- [x] 1.1 Add TeamBot tool handlers for `read_file`, `write_file`, `edit_file`, `execute_shell_command`, `browser_use`, and `get_current_time` under `src/teambot/agents/tools/`.
- [x] 1.2 Register the CoPaw-aligned tool subset in `src/teambot/agents/tools/builtin.py` with explicit `ToolManifest` metadata and risk levels.
- [x] 1.3 Keep `message_reply` as default safe action and gate optional parity extensions (`desktop_screenshot`, `send_file_to_user`) behind explicit feature flags.

## 2. Safety And Configuration Controls

- [x] 2.1 Ensure high-risk manifests are set for `execute_shell_command`, `write_file`, and `edit_file` so existing `ExecutionPolicyGate` evaluates before invocation.
- [x] 2.2 Add/refresh environment toggles for baseline open tools and optional parity extensions in runtime config usage.
- [x] 2.3 Update `.env.template` so every added/renamed/removed tool-related env key is reflected with defaults/examples.

## 3. Verification Coverage

- [x] 3.1 Add/extend tests for registry composition (enabled/disabled matrix and manifest risk levels).
- [x] 3.2 Add tests for normalized tool output envelopes on success, validation error, and blocked policy responses.
- [x] 3.3 Add tests for unified action execution fallback when selected tool is unavailable.

## 4. Documentation And Spec Validation

- [x] 4.1 Update `docs/agent-core-algorithm.md` to reflect the expanded built-in tool set and policy-gated behavior.
- [x] 4.2 Update `repo_wiki.md` to keep architecture/module responsibility and runtime flow in sync with the new tool surface.
- [x] 4.3 Run `openspec validate align-open-tools-with-copaw-baseline` and relevant test commands, then record any non-run items with reason.

## Verification Notes

- Ran: `openspec validate align-open-tools-with-copaw-baseline` (pass).
- Ran: `pytest -q tests/test_builtin_open_tools.py tests/test_action_policy.py tests/test_react_loop.py tests/test_routing.py` (9 passed, 1 skipped).
- Ran: `pytest -q` (29 passed, 4 skipped).
