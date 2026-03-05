# Code Structure (Canonical)

This is the single source of truth for TeamBot code layout.

## 1. Directory Layout

```text
src/teambot/
  app/                 # entrypoints (API/CLI/bootstrap)
  domain/              # shared business objects and state
  agents/              # agent runtime (react/tools/skills/mcp/providers/subagents)
  workflows/           # complex execution engine (optional path)
  channels/            # multi-channel adapters
  contracts/           # cross-module protocols/contracts
```

Current transition note:
- Existing code may still contain temporary legacy paths.
- New code MUST follow the layout above.

## 2. Dependency Direction

Allowed:
- `app -> agents/domain/contracts/channels/workflows`
- `channels -> agents/domain/contracts`
- `workflows -> agents/domain/contracts`
- `agents -> domain/contracts`

Disallowed:
- `domain -> agents/channels/workflows/providers`
- `agents -> channels`
- `contracts -> runtime implementations`

## 3. File Placement Rules

- Do not add new business `.py` files directly under `src/teambot/`.
- Shared DTO/state types go to `domain` (e.g. inbound/outbound/session).
- Storage logic goes to `domain/store`.
- Agent runtime logic goes to `agents`.
- Debug/utility runners should be under `app` (or a dedicated scripts area), not package root.

## 4. Documentation Rule

- Any structural change MUST update this file in the same change.
- Other docs should link here instead of redefining structure rules.
