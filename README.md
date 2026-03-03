# TeamBot Agent Core MVP

Minimal MVP for a TeamBot-style assistant with:

- Custom Agent Core runtime loop
- LangChain model adapter layer (multi-provider)
- Explicit skills registry (not prompt-only skills)
- Hard reply routing (`team_id + channel_id + thread_ts`)
- Event idempotency for duplicate deliveries

## Why this MVP

This repository is designed to address the pain points discussed earlier:

1. Reply must go back to the correct thread deterministically.
2. Skills must be explicit runtime modules.
3. Agent behavior should be orchestrated in deterministic runtime contracts, not ad-hoc loops.

## Architecture

Router/Planner/Agent Core focused diagrams:
- `docs/agent-runtime-architecture.md`

- `src/teambot/main.py`: FastAPI ingress/debug endpoints
- `src/teambot/agents/core/service.py`: application service that runs Agent Core runtime
- `src/teambot/agents/core/graph.py`: ReAct-style custom runtime (`reason -> act -> observe -> loop/compose_reply`)
- `src/teambot/agents/core/router.py`: reason node + route guards
- `src/teambot/agents/core/executor.py`: act/observe/compose nodes
- `src/teambot/agents/core/state.py`: initial `AgentState` builder
- `src/teambot/agents/planner.py`: planner abstraction (`RulePlanner` + optional dual-model `ReasoningModelPlanner`)
- `src/teambot/agents/providers/`: provider manager (`config/registry/router/normalize`)
- `src/teambot/agents/model_adapter.py`: compatibility shim around provider manager clients
- `src/teambot/agents/skills/`: skill registry + builtin skills
- `src/teambot/agents/tools/`: tool registry + builtin tool adapters
- `src/teambot/store.py`: in-memory conversation + idempotency store

## Run

```bash
cd /Users/nigelleong/Desktop/personal/langgraph-virtual-employee-mvp
python3.10 -m venv .venv310
source .venv310/bin/activate
pip install -r requirements-dev.txt
PYTHONPATH=src uvicorn teambot.main:app --reload
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

Send a message event:

```bash
curl -X POST http://127.0.0.1:8000/events/slack \
  -H 'Content-Type: application/json' \
  -d '{
    "event_id":"evt-100",
    "event_type":"message",
    "team_id":"T1",
    "channel_id":"C1",
    "thread_ts":"1710000000.0100",
    "user_id":"U1",
    "text":"/todo draft quarterly plan"
  }'
```

## Enable model planner (optional)

By default, TeamBot uses local `RulePlanner`.
If you set `AGENT_MODEL`, runtime planning uses the provider manager.
If you also set `ROUTER_MODEL`, the system uses dual-model routing:
router model for low-cost dispatch, agent model for deeper planning.

```bash
export AGENT_PROVIDER="openai-compatible"
export AGENT_MODEL="gpt-5-mini"
export AGENT_API_KEY="your_api_key"
export AGENT_BASE_URL="https://api.openai.com/v1"
export AGENT_TIMEOUT_SECONDS="20"
export AGENT_MAX_ATTEMPTS="2"
export AGENT_FALLBACKS_JSON='[
  {"provider":"anthropic","model":"claude-3-5-sonnet-latest","api_key":"your_api_key"}
]'

export ROUTER_PROVIDER="openai-compatible"
export ROUTER_MODEL="gpt-5-nano"
export ROUTER_API_KEY="your_api_key"
export ROUTER_BASE_URL="https://api.openai.com/v1"
export ROUTER_TIMEOUT_SECONDS="10"
export ROUTER_MAX_ATTEMPTS="2"
export ROUTER_FALLBACKS_JSON='[
  {"provider":"openai-compatible","model":"gpt-5-mini"}
]'
```

Planner response is constrained to structured JSON with:
- `selected_skill`
- `skill_input`
- `done`
- `final_message`
- `note`

Safety behavior:
- model failure -> fallback to `RulePlanner`
- invalid skill name -> fallback to `general_reply`
- max ReAct steps -> forced finish
- high-risk actions -> policy gate block by default

## .env support

The app auto-loads `.env` on startup (without overriding already exported env vars).

- Search order: current working directory `.env`, then project root `.env`

## CLI mode (interactive testing)

Use CLI mode for fast local interaction without HTTP calls:

```bash
PYTHONPATH=src python -m teambot.cli
```

Useful commands in CLI:
- `/help`
- `/reaction eyes`
- `/newthread`
- `/stream on`
- `/stream off`
- `/exit`

Enable token streaming in CLI at startup:

```bash
PYTHONPATH=src python -m teambot.cli --stream-model-tokens
```

## ReAct loop debug demo (interactive, full trace)

Use this when you need full per-turn debugging:
- model input/output per call (`system_prompt`, `payload`, parsed response)
- skill/tool invocation input state and output
- final runtime state and `execution_trace`

Start interactive debug REPL (no args):

```bash
PYTHONPATH=src python -m teambot.react_loop_demo
```

Then type text directly. For each turn it prints:
- `bot> ...` final reply
- human-readable summary report
- live progress events while model/tool calls are running
- token-level model stream while the model is generating

Interactive commands:
- `/help`
- `/newthread`
- `/reaction <name>`
- `/view summary|full`
- `/live on|off`
- `/exit`

One-shot mode is still available:

```bash
PYTHONPATH=src python -m teambot.react_loop_demo --text "/todo draft roadmap" --view full --pretty
```

To keep output short in one-shot mode:

```bash
PYTHONPATH=src python -m teambot.react_loop_demo --text "hello" --view summary
```

## Provider smoke test (router + agent)

Quickly test whether both model roles can be invoked with current env:

```bash
PYTHONPATH=src python -m teambot.provider_smoke_test --roles router,agent --pretty
```

You can test a single role:

```bash
PYTHONPATH=src python -m teambot.provider_smoke_test --roles agent --pretty
```

## Enable dynamic skills (optional)

Set `SKILLS_DIR` to auto-load skill plugins from a directory at startup.

```bash
export SKILLS_DIR="/absolute/path/to/skills"
```

Each `*.py` plugin supports either:
- `manifest` + `handle`
- `register(registry)`

Example plugin (`echo_skill.py`):

```python
manifest = {
    "name": "echo_dynamic",
    "description": "Echo dynamic skill",
}

def handle(state):
    return {"message": f"echo:{state['user_text']}"}
```

## CoPaw-style skill lifecycle

This repo now supports CoPaw-style skill directories:

- builtin: `src/teambot/agents/skills/packs`
- customized: `${CUSTOMIZED_SKILLS_DIR}` or `${WORKING_DIR}/customized_skills`
- active: `${ACTIVE_SKILLS_DIR}` or `${WORKING_DIR}/active_skills`

`active` skills are the runtime source of truth. On startup:

1. if active is empty, builtin/customized skills are synced into active
2. runtime registry is rebuilt using active skill names
3. active `SKILL.md` documents are injected into reasoning planner context

Env vars:

```bash
export WORKING_DIR="~/.teambot"
export ACTIVE_SKILLS_DIR=""
export CUSTOMIZED_SKILLS_DIR=""
```

Skill management APIs:

- `GET /skills`
- `POST /skills/sync?force=false`
- `POST /skills/{skill_name}/enable?force=false`
- `POST /skills/{skill_name}/disable`

## Tests

```bash
cd /Users/nigelleong/Desktop/personal/langgraph-virtual-employee-mvp
source .venv310/bin/activate
PYTHONPATH=src pytest -q
```

## Notes for production

This MVP intentionally keeps infra in memory. For production:

1. Replace `MemoryStore` with Postgres-backed conversation store.
2. Put a durable queue between ingress and worker (Redis Streams/Kafka/SQS).
3. Add outbox sender worker with retry and dead-letter policies.
4. Add skill permission/budget policy enforcement.

## CoPaw baseline reference

For architecture parity planning, see:

- `docs/copaw-baseline.md`
- `docs/framework-design.md`
- `docs/architecture-worklog.md`
- `docs/agent-core-migration.md`
