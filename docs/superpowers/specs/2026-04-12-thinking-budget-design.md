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

### Effort → Token Map (`src/teambot/providers/clients/native.py`)

```python
_THINKING_BUDGET_MAP: dict[str, int] = {
    "low":    4096,
    "medium": 8192,
    "high":   16384,
    "xhigh":  32768,
}
```

### Injection Logic (Anthropic only)

Applied in both `_invoke_anthropic` and `_invoke_anthropic_chat`:

```python
if self.endpoint.thinking_effort:
    budget = _THINKING_BUDGET_MAP[self.endpoint.thinking_effort]
    params["thinking"] = {"type": "enabled", "budget_tokens": budget}
    params["temperature"] = 1  # Anthropic requirement when thinking is enabled
```

OpenAI calls (`_invoke_openai_chat`) are unaffected — no thinking injection.

### Config Loaders (`src/teambot/providers/config.py`)

Both `_endpoint_from_config_dict` and `_endpoint_from_dict` read `thinking_effort` from the raw dict and pass it to `ProviderEndpoint`:

```python
thinking_effort = raw.get("thinking_effort") or None
```

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

- Unknown effort value (not in map): raise `ValueError` with message listing valid values
- `thinking_effort` set on non-Anthropic provider: silently ignored (no injection)

## Testing

- `test_thinking_budget_map_values` — effort → token mapping is correct for all 4 levels
- `test_thinking_effort_injects_thinking_block` — params contain `thinking` block and `temperature=1` when effort is set
- `test_no_thinking_effort_no_injection` — params have no `thinking` key when `thinking_effort=None`
- `test_openai_call_unaffected` — OpenAI path does not receive `thinking` block
- `test_unknown_effort_raises` — unknown effort string raises `ValueError`

## Files Changed

- `src/teambot/providers/base.py` — add field
- `src/teambot/providers/clients/native.py` — add map + injection
- `src/teambot/providers/config.py` — read field in both loader functions
- `config/config.json` — document new field (commented example, not enabled)
