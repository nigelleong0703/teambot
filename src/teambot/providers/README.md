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
- `config.py`: env parsing and profile binding assembly
- `clients/langchain.py`: LangChain client implementation and stream parsing
- `manager.py`: profile routing, failover, event emission, client registry, JSON extraction

## Environment Inputs

Recommended runtime env inputs:

- `RUNTIME_CONFIG_FILE`
- `ANTHROPIC_API_KEY`
- `OPENAI_API_KEY`
- `AGENT_HOME`

Legacy compatibility env groups still supported:

- `AGENT_*` for profile `agent`
- `SUMMARY_*` for profile `summary`

Canonical configuration is a single runtime config file:

- `RUNTIME_CONFIG_FILE`
  - points to repo-tracked `config/config.json`
  - provider config lives under:
    - `providers.models`
    - `providers.profiles`

Primary endpoint:

- `AGENT_MODEL` (required to enable profile `agent`)
- `AGENT_PROVIDER` (default: `openai-compatible`)
- `AGENT_API_KEY` (optional direct override)
- `AGENT_BASE_URL` (optional, auto default for openai-compatible/openai)
- `AGENT_TIMEOUT_SECONDS` (optional)
- `AGENT_MAX_ATTEMPTS` (optional)

- `SUMMARY_MODEL` (optional; enables profile `summary`)
- `SUMMARY_PROVIDER` (default: `openai-compatible`)
- `SUMMARY_API_KEY` (optional direct override)
- `SUMMARY_BASE_URL` (optional, auto default for openai-compatible/openai)
- `SUMMARY_TIMEOUT_SECONDS` (optional)
- `SUMMARY_MAX_ATTEMPTS` (optional)

Built-in fallback endpoints:

- `AGENT_FALLBACKS_JSON` array of objects:
  - `provider`, `model` (required)
  - `api_key`, `base_url`, `timeout_seconds`, `temperature` (optional)
- `SUMMARY_FALLBACKS_JSON` follows the same shape for profile `summary`

Canonical provider config shape inside `config/config.json`:

- `providers.models`
  - keys are reusable `model_id` values such as `main_sonnet`, `fast_haiku`
  - values are objects with:
    - `provider`, `model` (required to enable the definition)
    - `api_key`, `base_url`, `timeout_seconds`, `temperature` (optional)
    - string values inside `config/config.json` support `${ENV_VAR}` substitution at load time
    - `$${ENV_VAR}` escapes a literal placeholder without expansion
- `providers.profiles`
  - keys are profile names such as `agent`, `summary`, `extract`, `planner`
  - values may be:
    - a string model id: `"summary":"fast_haiku"`
    - an array of model ids for primary + fallbacks
    - an object with `model_id` or `model_ids`, plus optional `max_attempts`
  - built-in `AGENT_*` / `SUMMARY_*` bindings load first; same-name entries in `config/config.json` override them

Recommended repo layout:

- store canonical runtime config under:
  - `config/config.json`
- point `.env` at that file with:
  - `RUNTIME_CONFIG_FILE=./config/config.json`
- keep secrets in `.env` and reference them from config with templates such as:
  - `"api_key": "${ANTHROPIC_API_KEY}"`

Legacy compatibility:

- `MODEL_DEFINITIONS_JSON`, `MODEL_PROFILE_BINDINGS_JSON`, `MODEL_DEFINITIONS_FILE`, and `MODEL_PROFILE_BINDINGS_FILE` are still accepted for older configs
- `api_key_env` inside model definitions is still accepted for older configs
- `MODEL_PROFILES_JSON` is still accepted for older envs
- it is no longer the preferred advanced configuration path
- `AGENT_*` / `SUMMARY_*` remain as built-in shortcut inputs for the `agent` and `summary` profiles

Provider-level API key fallback when `AGENT_API_KEY` is empty:

- `openai-compatible` / `openai`: `OPENAI_API_KEY`
- `anthropic`: `ANTHROPIC_AUTH_TOKEN`, then `ANTHROPIC_API_KEY`
