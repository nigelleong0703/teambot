# API and Debug

## API Endpoints

- `GET /health`
- `POST /events/slack`
- `POST /events/{channel}`
- `POST /gateway/{channel}/events`
- `GET /events/whatsapp`
- `GET /gateway/whatsapp/events`
- `GET /skills`
- `GET /conversations`
- `POST /skills/sync`
- `POST /skills/{skill_name}/enable`
- `POST /skills/{skill_name}/disable`

Gateway ingress notes:
- Registered phase-1 HTTP channels: `whatsapp`, `slack`, `telegram`, `discord`, `feishu`
- Current scope is message ingress normalization only
- `/events/slack` remains as a compatibility path
- Slack ingress is handled by `slack-bolt` and accepts `url_verification` plus `event_callback`
- Telegram ingress is handled by `python-telegram-bot` update parsing and supports webhook secret-token validation
- Feishu ingress is handled by `lark-oapi` event dispatch and supports callback verification-token / signature validation
- WhatsApp ingress is handled by `pywa`; the GET routes serve the webhook challenge and POST validates `X-Hub-Signature-256`
- Discord ingress is handled by `discord-interactions.py` and supports interaction signature validation plus `PING` / application-command payloads

## Local Debug Utilities

- Interactive CLI:
  - `PYTHONPATH=src python -m teambot.app.cli`
  - inside CLI, run `/tools` to print runtime-enabled tools deterministically
  - use `--show-model-payload` to inspect model payload including registered tool schemas
- ReAct debug runner:
  - `PYTHONPATH=src python -m teambot.app.react_loop_demo`
- Provider smoke test:
  - `PYTHONPATH=src python -m teambot.app.provider_smoke_test --pretty`

## Notes

- Runtime model and behavior details are defined in:
  - `docs/agent-core-algorithm.md`
- Structure and dependency rules are defined in:
  - `docs/code-structure.md`
  - `docs/architecture-boundaries.md`
