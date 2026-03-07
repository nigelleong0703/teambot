# Providers Module

This module owns model provider wiring for the runtime.

## Supported Provider Values

- `openai-compatible`
- `openai`
- `anthropic`

Aliases normalized by code:

- `openai_compatible` -> `openai-compatible`

## Responsibilities by File

- `base.py`: dataclasses/protocols/errors (provider domain contracts)
- `registry.py`: provider catalog and normalization helpers
- `config.py`: env parsing and role binding assembly
- `clients/langchain.py`: LangChain client implementation and stream parsing
- `manager.py`: role routing, failover, event emission, client registry, JSON extraction

## Environment Inputs

Role prefix currently used:

- `AGENT_*` for `ROLE_AGENT`

Primary endpoint:

- `AGENT_MODEL` (required to enable role)
- `AGENT_PROVIDER` (default: `openai-compatible`)
- `AGENT_API_KEY` (optional direct override)
- `AGENT_BASE_URL` (optional, auto default for openai-compatible/openai)
- `AGENT_TIMEOUT_SECONDS` (optional)
- `AGENT_MAX_ATTEMPTS` (optional)

Fallback endpoints:

- `AGENT_FALLBACKS_JSON` array of objects:
  - `provider`, `model` (required)
  - `api_key`, `base_url`, `timeout_seconds`, `temperature` (optional)

Provider-level API key fallback when `AGENT_API_KEY` is empty:

- `openai-compatible` / `openai`: `OPENAI_API_KEY`
- `anthropic`: `ANTHROPIC_AUTH_TOKEN`, then `ANTHROPIC_API_KEY`
