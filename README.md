# TeamBot

TeamBot is an agent-first backend runtime for chat automation systems.
It focuses on deterministic ReAct execution, tools/skills orchestration, and clean extensibility for future multi-channel and multi-agent flows.
It now includes a channel-plugin gateway ingress skeleton for Slack, Telegram, Discord, WhatsApp, and Feishu HTTP message intake.

## Quick Start

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

python -m pip install -r requirements-dev.txt
cp .env.template .env
PYTHONPATH=src python -m uvicorn teambot.app.main:app --reload
```

## Docs

- Start here: `docs/README.md`
- Project overview and features: `docs/modules/project-overview.md`
- Setup and runtime commands: `docs/modules/getting-started.md`
- API and debug commands: `docs/modules/api-and-debug.md`
- Canonical architecture and runtime behavior:
  - `docs/code-structure.md`
  - `docs/architecture-boundaries.md`
  - `docs/agent-core-algorithm.md`

## Notes

- `docs/plans/` is system-managed.
- `openspec/` is system-managed.
