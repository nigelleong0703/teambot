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
This repo runs directly from `src/` and does not require an editable package install.

## 2) Configure `.env`

```bash
cp .env.template .env
```

Fill required values in `.env` based on your provider and runtime needs.
CLI and API startup now auto-load `.env` from the current working directory and parent directories.
Shell-exported environment variables still win and are not overridden by `.env`.

Important groups:
- canonical runtime config file: `RUNTIME_CONFIG_FILE`
- provider secrets: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`
- agent home: `AGENT_HOME`
- optional legacy override envs: `AGENT_*`, `SUMMARY_*`, `TOOLS_*`, `MCP_*`, policy override envs

`AGENT_HOME` is the agent's only working root. Runtime paths are derived from it:
- prompt files: `AGENT_HOME/system/AGENTS.md`, `SOUL.md`, `PROFILE.md`
- optional long-term memory file: `AGENT_HOME/system/memory.md`
- tool working directory: `AGENT_HOME/work`
- runtime store database: `AGENT_HOME/state/teambot.sqlite`
- shared skill docs: `~/.teambot/skills`
- agent-local skill docs: `AGENT_HOME/skills`
- dynamic skill plugins: `AGENT_HOME/system/skills`

Runtime config now has two paths:
- canonical: store provider/tools/policy/mcp defaults in `config/config.json`, then point `.env` at that file
- legacy override path: set built-in env groups directly when you need a machine-local override

Example canonical `.env`:

```env
RUNTIME_CONFIG_FILE=./config/config.json
ANTHROPIC_API_KEY=...
```

Example `config/config.json`:

```json
{
  "providers": {
    "models": {
      "main_sonnet": {
        "provider": "anthropic",
        "model": "claude-sonnet",
        "api_key": "${ANTHROPIC_API_KEY}"
      },
      "fast_haiku": {
        "provider": "anthropic",
        "model": "claude-haiku",
        "api_key": "${ANTHROPIC_API_KEY}"
      }
    },
    "profiles": {
      "agent": "main_sonnet",
      "summary": "fast_haiku",
      "extract": "fast_haiku"
    }
  },
  "tools": {
    "profile": "external_operation",
    "namesake_strategy": "skip",
    "enable_echo_tool": false,
    "enable_exec_alias": false,
    "exec_timeout_seconds": 20,
    "browser_timeout_seconds": 10,
    "tool_output_max_chars": 4000
  },
  "policy": {
    "allow_high_risk_actions": false,
    "high_risk_allowed_actions": []
  },
  "mcp": {
    "enabled": false,
    "servers": []
  }
}
```

`config/config.json` supports `${ENV_VAR}` substitution inside string values. Use `$${ENV_VAR}` if you need a literal placeholder without expansion.

Built-in env shortcuts remain supported for compatibility, but new setups should prefer `config/config.json` + `.env` secrets.

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
