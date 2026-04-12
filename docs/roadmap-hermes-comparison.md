# Helm vs Hermes — Improvement Roadmap

> Analysis of what hermes-agent does that Helm can adopt, what Helm already does better, and what to build next.

---

## What Helm Already Does Better

Don't touch these — they're cleaner than hermes:

| Area | Helm advantage |
|------|---------------|
| **Agent loop** | `loop.py` is stateless — `run()` returns `(text, messages)` instead of mutating. Hermes is provider-specific and heavy. |
| **Provider abstraction** | `ProviderEndpoint` + `ProviderProfileBinding` is unified. Hermes spreads logic across multiple adapter files. |
| **Architecture** | Clear module boundaries: `agent/`, `memory/`, `providers/`, `skills/`, `channels/`. Hermes has a 8700-line `cli.py`. |
| **Memory compaction** | `RollingSummaryCompactionEngine` is clean. Needs enhancement, not replacement. |

---

## Gaps — What to Build

### 1. Toolset Composition System ⭐ HIGH

**What hermes has:** `toolsets.py` (568 lines) — composable, hierarchical tool sets per platform/channel. `debugging` inherits `web` + `file`. Each channel (Slack, Discord, CLI) gets a different toolset.

**What Helm lacks:** All tools are equally available everywhere. No way to say "Slack gets read-only tools, CLI gets full access."

**How to adopt:**
- Create `src/teambot/toolsets.py` with `Toolset` dataclass (name, tools, inherits)
- Add `resolve_toolset(name)` that flattens inheritance
- Wire toolset into `AgentService` based on channel type

**Reference:** `hermes-agent/toolsets.py:392-450`

---

### 2. SQLite Session Storage + Full-Text Search ⭐ HIGH

**What hermes has:** `hermes_state.py` — SQLite with WAL mode, FTS5 full-text search across all messages, cost tracking per session (tokens, estimated_cost_usd), session parent chaining for compression.

**What Helm lacks:** No FTS, no cost tracking, no session analytics.

**How to adopt:**
- Extend memory store to use SQLite (WAL mode)
- Add FTS5 virtual table: `CREATE VIRTUAL TABLE messages_fts USING fts5(...)`
- Add columns: `source TEXT` (cli/slack/telegram), `cost_usd REAL`, `parent_session_id TEXT`

**Reference:** `hermes-agent/hermes_state.py:36-91`

---

### 3. Trajectory Compression with Protected Turns ⭐ MEDIUM

**What hermes has:** `trajectory_compressor.py` — configurable token budgets, always protects first N and last N turns, compresses only the middle, async parallel processing, per-trajectory metrics.

**What Helm has:** `compaction.py` with rolling summary — works but no budget awareness, no protected-turn strategy.

**How to adopt:**
- Add `CompressionConfig` dataclass: `target_max_tokens`, `protect_first_n`, `protect_last_n`
- Implement middle-turn protection in `RollingSummaryCompactionEngine`
- Add compression ratio metrics per session

**Reference:** `hermes-agent/trajectory_compressor.py:54-150`

---

### 4. Thinking Budget Support ⭐ MEDIUM

**What hermes has:** Maps thinking effort levels to token budgets — `xhigh: 32k`, `high: 16k`, `medium: 8k`, `low: 4k`. Detects model capability. Passes `budget_tokens` in API payload.

**What Helm lacks:** No thinking budget — extended thinking calls fail or get ignored.

**How to adopt:**
- Add `thinking_budget_tokens: int | None` to `ProviderEndpoint`
- Add `thinking_effort: str | None` (xhigh/high/medium/low) to config
- Map effort → tokens in `NativeProviderClient._invoke_anthropic_chat()`

**Reference:** `hermes-agent/agent/anthropic_adapter.py:30-90`

---

### 5. Skill Metadata Format ⭐ MEDIUM

**What hermes has:** SKILL.md files with YAML frontmatter — `name`, `description`, `version`, `platforms`, `prerequisites`, `tags`. Progressive disclosure: list shows only metadata, full content loads on demand.

**What Helm has:** Raw `SKILL.md` files with no structure, no version, no platform filtering.

**How to adopt:**
- Add frontmatter parser to `SkillManifest` (pyyaml)
- Support `platforms: [macos, linux]` filtering in `SkillRegistry.discover()`
- Add `prerequisites: [skill-name]` checking before activation
- Move skills to `$AGENT_HOME/skills/` so they're user-managed, not in src/

---

### 6. ACP Protocol (Agent Communication Protocol) ⭐ MEDIUM

**What hermes has:** `acp_adapter/` — full ACP server implementation. Enables other agents and editors to connect to Helm as a service. Supports session forking, MCP server registration, slash command palette.

**What Helm lacks:** No agent-to-agent communication protocol. Gateway handles channels but not agent clients.

**How to adopt:**
- Create `src/teambot/acp_adapter/` mirroring hermes structure
- Implement: `initialize`, `new_session`, `message`, `set_model`, `fork_session`
- Add `/help`, `/tools`, `/reset`, `/compact` slash commands via ACP

**Reference:** `hermes-agent/acp_adapter/server.py:92-215`

> This is the foundation for "team of agents" — each Helm instance connects to others via ACP.

---

### 7. Skill Creation Tools ⭐ LOW

**What hermes has:** `/skill-name` slash commands, `skill_create` / `skill_edit` tools, plan generation at `$HOME/.hermes/plans/`.

**What Helm lacks:** Skills are code-registered only. No way for the agent to create/edit its own skills from chat.

**How to adopt:**
- Add `skill_create(name, content)` and `skill_edit(name, patch)` as tools
- Add `/plan` slash command that writes a timestamped markdown plan to `$AGENT_HOME/plans/`
- Hook into `SkillRegistry` for hot-reload after creation

---

## Implementation Order

```
Phase 1 (foundation)
├── Toolset composition system
├── SQLite + FTS session storage
└── Thinking budget support

Phase 2 (memory)
├── Trajectory compression with protected turns
└── Skill metadata format + user-managed skills dir

Phase 3 (multi-agent)
├── ACP protocol
└── Skill creation tools
```

---

## What NOT to Adopt from Hermes

| Hermes thing | Why not |
|---|---|
| `cli.py` (8700 lines) | Helm's modular structure is better |
| Provider-specific adapters | Helm's unified `ProviderEndpoint` is cleaner |
| Custom message format | Stay OpenAI-compatible |
| Flat repo structure | Helm's `src/teambot/` boundaries are superior |
