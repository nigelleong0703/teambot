# Thinking Budget Support Design

**Date:** 2026-04-12
**Status:** Approved

## Overview

Add `thinking_effort` to `ProviderEndpoint` so Anthropic extended thinking can be enabled per model via `config.json`. When set, the provider client injects the `thinking` block into the API payload automatically.

## Architecture

`ProviderEndpoint` gains one new optional field. The native client reads it and injects the Anthropic-format thinking block. Config loaders propagate it from `config.json`. No changes to `AgentLoop`, `AgentService`, or any caller.

## Components

### ProviderEndpoint (`src/teambot/providers/base.py`)

Add one field:

```python
thinking_effort: str | None = None  # "low" | "medium" | "high" | "xhigh"
```

### Effort → Token Maps (`src/teambot/providers/clients/native.py`)

```python
_THINKING_BUDGET_MAP: dict[str, int] = {
    "low":    4096,
    "medium": 8192,
    "high":   16384,
    "xhigh":  32768,
}

# max_tokens must be strictly greater than budget_tokens (Anthropic requirement).
# Set to budget_tokens + 4096 to leave room for the actual response.
_THINKING_MAX_TOKENS_MAP: dict[str, int] = {
    "low":    8192,
    "medium": 12288,
    "high":   20480,
    "xhigh":  36864,
}
```

### Injection Logic (Anthropic only)

Applied in both `_invoke_anthropic` and `_invoke_anthropic_chat`, **before** the streaming branch (`if on_token is not None`), so that the mutated `params` dict flows into `_invoke_anthropic_stream` automatically:

```python
if self.endpoint.thinking_effort:
    budget = _THINKING_BUDGET_MAP[self.endpoint.thinking_effort]
    params["thinking"] = {"type": "enabled", "budget_tokens": budget}
    params["temperature"] = 1        # Anthropic requirement; overrides any configured temperature
    params["max_tokens"] = _THINKING_MAX_TOKENS_MAP[self.endpoint.thinking_effort]
```

No changes to `_invoke_anthropic_stream` — it receives the already-mutated `params` dict.

OpenAI calls (`_invoke_openai_chat`) are unaffected — no thinking injection.

### Config Loaders (`src/teambot/providers/config.py`)

Three paths exist. All three are updated:

**`_endpoint_from_config_dict`** (used by `config/config.json` model definitions):
```python
thinking_effort = raw.get("thinking_effort") or None
```

**`_endpoint_from_dict`** (used by `{PREFIX}_FALLBACKS_JSON` env var fallback endpoints):
```python
thinking_effort = raw.get("thinking_effort") or None
```

**`_build_primary_endpoint`** (used by `AGENT_MODEL` / `SUMMARY_MODEL` env var path):
```python
thinking_effort = os.getenv(f"{prefix}_THINKING_EFFORT") or None
```
This adds `AGENT_THINKING_EFFORT` and `SUMMARY_THINKING_EFFORT` env var support.

### config.json

New optional field per model definition:

```json
"agent_default": {
  "provider": "anthropic",
  "model": "claude-opus-4-6",
  "api_key": "${ANTHROPIC_API_KEY}",
  "thinking_effort": "high"
}
```

Not enabled by default. Omitting the field = no thinking.

## Data Flow

```
config.json "thinking_effort": "high"
    → _endpoint_from_config_dict reads field
    → ProviderEndpoint.thinking_effort = "high"
    → NativeProviderClient._invoke_anthropic_chat builds params
    → params["thinking"] = {"type": "enabled", "budget_tokens": 16384}
    → params["temperature"] = 1
    → Anthropic API call with extended thinking enabled
```

## Error Handling

- Unknown effort value (not in map): raise `ValueError` at config-load time (in the loader function), not at invocation time. Message lists valid values.
- `thinking_effort` set on non-Anthropic provider: silently ignored (no injection)
- `temperature` configured on the same endpoint: silently overridden to `1` when thinking is enabled. This is documented in `config.json` comments.

## Testing

- `test_thinking_budget_map_values` — effort → budget token mapping correct for all 4 levels; max_tokens > budget_tokens for each
- `test_thinking_effort_injects_thinking_block` — non-streaming path: params contain `thinking` block, `temperature=1`, and correct `max_tokens`
- `test_thinking_effort_injects_thinking_block_streaming` — streaming path (on_token provided): stream receives thinking block and `temperature=1`
- `test_no_thinking_effort_no_injection` — params have no `thinking` key when `thinking_effort=None`
- `test_openai_call_unaffected` — OpenAI path does not receive `thinking` block even when `thinking_effort` is set
- `test_unknown_effort_raises_at_config_load` — unknown effort string raises `ValueError` during config loading
- `test_endpoint_from_dict_loads_thinking_effort` — fallback endpoint loaded via `_endpoint_from_dict` carries `thinking_effort`

## Files Changed

- `src/teambot/providers/base.py` — add `thinking_effort` field; update `key` property to include it
- `src/teambot/providers/clients/native.py` — add maps + injection in both `_invoke_anthropic` and `_invoke_anthropic_chat`
- `src/teambot/providers/config.py` — read field in all three loader functions; add `AGENT_THINKING_EFFORT` / `SUMMARY_THINKING_EFFORT` env var support
- `config/config.json` — document new field (commented example, not enabled)

## Out of Scope

- Thinking + tool use interactions (Anthropic model-specific constraints not addressed here)
- Per-request thinking effort override (always set at endpoint level via config)
