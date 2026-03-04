# Agent Core Migration Notes

## Summary

This migration replaces LangGraph as the primary runtime orchestrator with a custom
Agent Core loop while retaining ReAct semantics.

Execution path is now:

`reason -> act -> observe -> loop/compose`

## Operator Impact

### 1. Model Configuration

Use generic model environment variables:

- `AGENT_PROVIDER`, `AGENT_MODEL`, `AGENT_API_KEY`, `AGENT_BASE_URL`, `AGENT_TIMEOUT_SECONDS`
- `AGENT_MAX_ATTEMPTS` (bounded failover attempts)
- `AGENT_FALLBACKS_JSON` (ordered fallback providers)

### 2. Risk Policy Configuration

- `ALLOW_HIGH_RISK_ACTIONS` (`true|false`, default false)
- `HIGH_RISK_ALLOWED_ACTIONS` (comma-separated action names)

High-risk actions are blocked by default.

### 3. Optional Builtin Tool Actions

- `ENABLE_ECHO_TOOL=true` enables low-risk debug tool action `tool_echo`
- `ENABLE_EXEC_TOOL=true` registers high-risk placeholder action `exec_command`

### 4. Skills Lifecycle

No behavioral change to lifecycle directories:

- builtin: `src/teambot/agents/skills/packs`
- customized: `${CUSTOMIZED_SKILLS_DIR}` or `${WORKING_DIR}/customized_skills`
- active: `${ACTIVE_SKILLS_DIR}` or `${WORKING_DIR}/active_skills`

## Verification Checklist

1. Run tests: `./.venv310/bin/python -m pytest -q`
2. Verify health endpoint: `GET /health`
3. Verify message path: `POST /events/slack` with `event_type=message`
4. Verify reaction path: `POST /events/slack` with `event_type=reaction_added`
5. If high-risk tools are configured, verify policy block behavior in logs/reply text
