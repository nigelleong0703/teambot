# Agent Notes

## Reference Paths
- /Users/nigelleong/Desktop/personal/CoPaw/src/copaw

## Environment Template Policy
- Always keep `/Users/nigelleong/Desktop/personal/langgraph-teambot-mvp/.env.template` up to date.
- Any new/renamed/removed environment variable in code or docs MUST be reflected in `.env.template` in the same change.
- `.env.template` is the single source of truth for expected runtime env keys and defaults/examples.
- Do not commit secrets. Real values go in local `.env`, not in `.env.template`.

## Core Algorithm Documentation Policy
- Canonical algorithm document: `/Users/nigelleong/Desktop/personal/teambot-mvp/docs/agent-core-algorithm.md`.
- This file is the source of truth for Agent Core runtime behavior (reason/act/observe/compose, planner contract, prompts, and streaming behavior).
- Any change to core algorithm behavior MUST update `docs/agent-core-algorithm.md` in the same change.
- If design flaws are identified, add/update them in the "Known Design Problems" section of that document.

## Documentation Structure Policy
- Canonical docs entrypoint: `docs/README.md`.
- Code/documentation structure source of truth: `docs/code-structure.md`.
- Keep docs layered by purpose:
  - Canonical current-state docs stay under `docs/` root.
  - Reference material stays under `docs/references/`.
  - Historical/obsolete docs move to `docs/archive/` (do not delete if still useful for traceability).
- `docs/plans/` is system-managed workflow content and MUST NOT be reorganized.
- `openspec/` is system-managed workflow content and MUST NOT be reorganized.
- Any architecture/runtime/documentation policy change MUST update:
  - `docs/README.md`
  - `docs/code-structure.md`
  - `repo_wiki.md` (when onboarding/runtime flow is impacted)

## Branch and Commit Naming Policy
- Follow normal, readable naming conventions for both branch names and commit messages.
- New features or major behavior changes MUST be developed on a dedicated branch first; do not implement them directly on `main`.
- Open a PR from the feature branch and merge only after review/verification gates are satisfied.
- Branch names SHOULD use lowercase kebab-case and include a type prefix:
  - `feat/<short-description>`
  - `fix/<short-description>`
  - `docs/<short-description>`
  - `refactor/<short-description>`
  - `chore/<short-description>`
- Commit messages SHOULD follow Conventional Commits style:
  - `feat: ...`
  - `fix: ...`
  - `docs: ...`
  - `refactor: ...`
  - `chore: ...`
- Keep branch and commit scope aligned with the actual change (no misleading prefixes).
- Avoid vague names like `update`, `test`, or `misc`; always describe what changed.

## Repo Wiki Maintenance Policy
- Canonical onboarding wiki: `/Users/nigelleong/Desktop/personal/teambot-mvp/repo_wiki.md`.
- `repo_wiki.md` MUST be continuously maintained and kept in sync with the current repository structure and runtime flow.
- Any change affecting architecture, module responsibilities, core execution flow, planner/provider behavior, or key run/debug commands MUST update `repo_wiki.md` in the same change.
- Do not allow documentation drift: if code and `repo_wiki.md` conflict, update the wiki immediately.

## AI-First Code Control Policy
- Default assumption: most implementation changes are AI-generated and MUST be tightly controlled.
- No hidden behavior changes: avoid "bonus refactors" unless explicitly requested.
- Keep diffs minimal and task-scoped; do not modify unrelated files.
- Prefer deterministic code paths over implicit magic behavior.
- Any risky change (runtime flow, planner logic, provider routing, execution policy) must include:
  - What changed
  - Why it changed
  - How to rollback
- Do not introduce new dependencies unless necessary; if added, justify in PR/commit message.

## Change Safety Rules
- Before editing, identify exact target files and keep the edit set small.
- Preserve backward compatibility unless breakage is explicitly approved.
- Do not silently rename public functions, env keys, API fields, or skill names.
- If env keys are added/renamed/removed, update `.env.template` in the same change.
- If behavior changes, add/update tests in the same change.
- If algorithm or flow changes, update:
  - `docs/agent-core-algorithm.md`
  - `repo_wiki.md`

## Testing and Verification Gate
- Minimum gate before merge:
  - Relevant unit/integration tests pass
  - No obvious regression in core flow (`reason -> act -> observe -> compose_reply`)
  - Documentation updated for behavior changes
- If tests cannot run, explicitly document:
  - What was not run
  - Why it was not run
  - What should be run later

## PR/Commit Quality Gate
- Every change should be easy to review in small commits.
- Commit messages must describe actual behavior change, not vague wording.
- For logic changes, include at least one concrete before/after example in PR description.
- Reject commits that mix refactor + feature + docs without clear separation.
