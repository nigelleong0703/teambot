# Getting Started

## 1) Environment Setup

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

python -m pip install -r requirements-dev.txt
```

Optional editable install:

```bash
python -m pip install -e ".[dev]"
```

## 2) Configure `.env`

```bash
cp .env.template .env
```

Fill required values in `.env` based on your provider and runtime needs.
CLI and API startup now auto-load `.env` from the current working directory and parent directories.
Shell-exported environment variables still win and are not overridden by `.env`.

Important groups:
- provider: `AGENT_PROVIDER`, `AGENT_MODEL`, `AGENT_API_KEY`, `AGENT_BASE_URL`
- agent home: `AGENT_HOME`
- tools: `TOOLS_PROFILE`, `TOOLS_NAMESAKE_STRATEGY`
- mcp: `MCP_ENABLED`, `MCP_SERVERS_JSON`
- policy: `ALLOW_HIGH_RISK_ACTIONS`, `HIGH_RISK_ALLOWED_ACTIONS`

`AGENT_HOME` is the agent's only working root. Runtime paths are derived from it:
- prompt files: `AGENT_HOME/system/AGENTS.md`, `SOUL.md`, `PROFILE.md`
- tool working directory: `AGENT_HOME/work`
- shared skill docs: `~/.teambot/skills`
- agent-local skill docs: `AGENT_HOME/skills`
- dynamic skill plugins: `AGENT_HOME/system/skills`

## 3) Run API

```bash
PYTHONPATH=src python -m uvicorn teambot.app.main:app --reload
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

## 4) Run CLI

```bash
PYTHONPATH=src python -m teambot.app.cli
```

Optional: run CLI with tool config JSON and profile override:

```bash
PYTHONPATH=src python -m teambot.app.cli --tools-config ./tools.json --tools-profile external_operation
```

Example `tools.json`:

```json
{
  "profile": "external_operation",
  "namesake_strategy": "skip",
  "overrides": {
    "enable": ["get_current_time"],
    "disable": ["execute_shell_command"]
  },
  "extras": {
    "enable_echo_tool": false,
    "enable_exec_alias": false
  }
}
```

## 5) Run Tests

```bash
PYTHONPATH=src pytest -q
```

## 6) Run TUI

```bash
PYTHONPATH=src python -m teambot.app.tui
```

Optional: run TUI with tool config JSON and profile override:

```bash
PYTHONPATH=src python -m teambot.app.tui --tools-config ./tools.json --tools-profile external_operation
```

TUI notes:
- TUI is terminal-native; it does not take over the terminal with an alternate-screen full-screen app.
- Startup prints a TeamBot welcome panel, then returns to a normal `❯` prompt.
- Transcript output stays in the terminal scrollback, so text selection and native scrolling still work.
- Live provider reasoning collapses into a simple `✻ Thinking...` line.
- Live provider answer tokens grow the current `⏺ ...` line in-place.
- CLI and TUI share one slash-command dispatcher in `src/teambot/app/slash_commands.py`.
- Core user-facing slash commands:
  - `/help`
  - `/skills`
  - `/skills sync [--force]`
  - `/skills enable <name>`
  - `/skills disable <name>`
  - `/newthread`
  - `/stream on|off`
  - `/reaction <name>`
  - `/exit`
- `/tools` is intentionally not exposed in the user-facing command set.
