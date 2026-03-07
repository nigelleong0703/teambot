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

This editable install now includes the TUI dependency (`textual`).

## 2) Configure `.env`

```bash
cp .env.template .env
```

Fill required values in `.env` based on your provider and runtime needs.
CLI and API startup now auto-load `.env` from the current working directory and parent directories.
Shell-exported environment variables still win and are not overridden by `.env`.

Important groups:
- provider: `AGENT_PROVIDER`, `AGENT_MODEL`, `AGENT_API_KEY`, `AGENT_BASE_URL`
- tools: `TOOLS_PROFILE`, `TOOLS_NAMESAKE_STRATEGY`
- skills: `WORKING_DIR`, `ACTIVE_SKILLS_DIR`, `CUSTOMIZED_SKILLS_DIR`, `SKILLS_DIR`
- mcp: `MCP_ENABLED`, `MCP_SERVERS_JSON`
- policy: `ALLOW_HIGH_RISK_ACTIONS`, `HIGH_RISK_ALLOWED_ACTIONS`

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
- TUI uses a Claude-like single-column workbench instead of explicit debug sections.
- Top bar is intentionally minimal; it shows the workspace and only adds `working` while a run is active.
- Empty state shows a compact welcome panel with workspace/model context and quick-start tips, without forcing a vertical scrollbar.
- Composer is a single-line Claude-like prompt row with a leading `>` glyph.
- Live provider reasoning tokens remain available at the runtime-event layer but are not shown in the default TUI.
- Live provider answer tokens grow the current final answer line.
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
