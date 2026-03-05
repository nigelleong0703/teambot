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
   - Runtime algorithm source of truth.

## Modules (project details)

- `modules/project-overview.md`
  - What TeamBot is, current feature set, use cases, and high-level module map.
- `modules/getting-started.md`
  - Environment setup, `.env` groups, run commands, and test commands.
- `modules/api-and-debug.md`
  - API endpoint list and local debug utilities.

## Reference Docs

- `references/copaw-baseline.md`
  - CoPaw baseline notes used for parity alignment.

## Archived Docs (historical context)

- `archive/migrations/agent-core-migration.md`
- `archive/architecture/agent-runtime-architecture.md`
- `archive/architecture/framework-design.md`
- `archive/architecture/architecture-worklog.md`

## Maintenance Rules

- Any structural/runtime behavior change must update the canonical docs in the same change.
- Avoid adding loose markdown files directly under `docs/` unless they are canonical docs.
- Move outdated docs to `docs/archive/` instead of deleting them.
