# Post-Change Next Steps

## Goal

Track the work that is still genuinely unfinished after the agent runtime, CLI/TUI transcript flow, skills context injection, and package structure refactor landed.

## What Is Already Landed

These items are no longer backlog items:

1. Native model tool-calling runtime
   - Done
   - Tool schemas are active and the reasoner can emit native tool calls or final text.
2. Active skill docs in reasoner context
   - Done
   - Skill docs are injected into reasoner payload/prompt as guidance context.
3. CLI/TUI skills management surface
   - Done
   - CLI and TUI both expose `/skills`, `/skills sync`, `/skills enable`, `/skills disable`.
4. Runtime transcript/event stream
   - Done
   - `RuntimeEvent` is the shared event contract for transcript-style clients.
5. Claude-style TUI baseline
   - Done
   - TUI is present and consumes the same runtime event stream as the CLI.
6. Conversation history injection
   - Done
   - Prior stored turns are now passed into reasoner payload as bounded `recent_turns`.
7. Modular memory context wiring
   - Done
   - Transcript access, long-term memory loading, and reasoner memory injection now flow through `src/teambot/memory/`.
8. Provider-backed rolling-summary compaction
   - Done
   - Older turns are compacted into `conversation_state.rolling_summary` through the provider-backed session-memory path while recent raw turns remain directly injectable.

## Current Remaining Work

This is the actual outstanding backlog based on the current canonical docs.

1. Implement a real browser backend behind the new `browser(action=...)` surface
   - Current gap:
     - TeamBot now separates `web_fetch` from `browser`, but `browser` still returns MVP placeholder responses instead of driving a real browser.
   - Why it matters:
     - The tool contract is now clearer, but real browsing workflows still cannot be completed end-to-end.

2. Harden execution policy beyond the current high-risk gate
   - Current gap:
     - Path sandbox rules, command budgets, and stronger per-tool governance are still missing.
   - Why it matters:
     - The current policy layer is useful, but still too coarse for stricter local execution control.

3. Strengthen working-directory prompt contract
   - Current gap:
     - There is still no strict-mode enforcement that requires `AGENTS.md` (and optionally `SOUL.md`) before agent-model execution.
   - Why it matters:
     - Prompt discipline still depends too much on fallback behavior.

4. Improve provider/runtime performance controls
   - Current gap:
     - No first-class knobs yet for lower-latency reasoning modes such as lower step budgets, smaller answer budgets, or provider-specific low-reasoning controls.
   - Why it matters:
     - Latency is still mostly driven by provider/model choice, prompt size, and default ReAct loop depth.

5. Expand platform capabilities
   - Current gap:
     - Channel adapters, cron scheduling, and richer memory/fact infrastructure are still not implemented.
   - Why it matters:
     - The runtime core is in place, but the surrounding platform surface is still incomplete.

## Recommended Priority Order

1. Real browser automation protocol
2. Execution policy hardening
3. Provider/runtime performance controls
4. Strict prompt contract
5. Channels / cron / richer memory infrastructure

## Runtime Sanity Checklist

Use this after each future runtime change:

1. Run tests
   - `pytest -q`
2. Run CLI
   - `python -m teambot.app.cli --tools-profile external_operation --show-model-payload`
3. In CLI, verify
   - `/skills` shows the expected active skill state
   - `check my current time` triggers `get_current_time`
   - debug payload still shows the model request and tool schema data
4. Run TUI
   - `python -m teambot.app.tui --tools-profile external_operation`
5. In TUI, verify
   - transcript renders correctly
   - live final answer still updates
   - slash commands remain consistent with CLI

## Definition of Done (for each future change)

- Tests pass
- Runtime behavior is verified through a real CLI or TUI run
- Docs are updated (`docs/*` and `repo_wiki.md` when runtime flow changes)
- Branch is merged and cleaned up
