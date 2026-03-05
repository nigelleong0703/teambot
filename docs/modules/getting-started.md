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
