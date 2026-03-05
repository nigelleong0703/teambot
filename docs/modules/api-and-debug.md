# API and Debug

## API Endpoints

- `GET /health`
- `POST /events/slack`
- `GET /skills`
- `GET /conversations`
- `POST /skills/sync`
- `POST /skills/{skill_name}/enable`
- `POST /skills/{skill_name}/disable`

## Local Debug Utilities

- Interactive CLI:
  - `PYTHONPATH=src python -m teambot.cli`
- ReAct debug runner:
  - `PYTHONPATH=src python -m teambot.react_loop_demo`
- Provider smoke test:
  - `PYTHONPATH=src python -m teambot.provider_smoke_test --pretty`

## Notes

- Runtime model and behavior details are defined in:
  - `docs/agent-core-algorithm.md`
- Structure and dependency rules are defined in:
  - `docs/code-structure.md`
  - `docs/architecture-boundaries.md`
