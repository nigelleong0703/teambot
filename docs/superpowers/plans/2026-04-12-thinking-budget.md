# Thinking Budget Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `thinking_effort` config field to `ProviderEndpoint` so Anthropic extended thinking can be enabled per model.

**Architecture:** One new optional field on `ProviderEndpoint`; `NativeProviderClient` reads it and injects the Anthropic thinking block into params before streaming/non-streaming branches; all three config loaders propagate it. No changes to `AgentLoop`, `AgentService`, or any caller.

**Tech Stack:** Python 3.11+, anthropic SDK, pytest

---

## Chunk 1: ProviderEndpoint field + config loaders

### Task 1: Write failing tests for ProviderEndpoint and config loaders

**Files:**
- Create: `tests/test_thinking_budget.py`

- [ ] **Step 1: Write the complete test file (all imports at top)**

```python
# tests/test_thinking_budget.py
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from teambot.providers.base import ProviderConfigError, ProviderEndpoint
from teambot.providers.clients.native import (
    NativeProviderClient,
    _THINKING_BUDGET_MAP,
    _THINKING_MAX_TOKENS_MAP,
)
from teambot.providers.config import (
    _endpoint_from_dict,
    load_provider_settings_from_env,
)


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------

def _make_endpoint(**kwargs) -> ProviderEndpoint:
    defaults = dict(provider="anthropic", model="claude-opus-4-6")
    defaults.update(kwargs)
    return ProviderEndpoint(**defaults)


def _make_client(thinking_effort: str | None = None) -> NativeProviderClient:
    ep = _make_endpoint(api_key="test-key", thinking_effort=thinking_effort)
    return NativeProviderClient(ep)


# -------------------------------------------------------------------
# ProviderEndpoint field + key
# -------------------------------------------------------------------

def test_thinking_effort_defaults_to_none() -> None:
    ep = _make_endpoint()
    assert ep.thinking_effort is None


def test_thinking_effort_stored_correctly() -> None:
    ep = _make_endpoint(thinking_effort="high")
    assert ep.thinking_effort == "high"


def test_key_includes_thinking_effort_when_set() -> None:
    ep = _make_endpoint(thinking_effort="high")
    assert "high" in ep.key


def test_key_differs_between_effort_levels() -> None:
    ep_none = _make_endpoint()
    ep_high = _make_endpoint(thinking_effort="high")
    ep_low = _make_endpoint(thinking_effort="low")
    assert ep_none.key != ep_high.key
    assert ep_high.key != ep_low.key


# -------------------------------------------------------------------
# Config loaders
# -------------------------------------------------------------------

def test_endpoint_from_config_dict_loads_thinking_effort(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "MODEL_DEFINITIONS_JSON",
        '{"thinking-model":{"provider":"anthropic","model":"claude-opus-4-6",'
        '"thinking_effort":"high"}}',
    )
    monkeypatch.setenv("MODEL_PROFILE_BINDINGS_JSON", '{"agent":"thinking-model"}')

    settings = load_provider_settings_from_env()
    endpoint = settings.get_profile_binding("agent").endpoints[0]

    assert endpoint.thinking_effort == "high"


def test_endpoint_from_config_dict_thinking_effort_none_when_omitted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "MODEL_DEFINITIONS_JSON",
        '{"plain-model":{"provider":"anthropic","model":"claude-opus-4-6"}}',
    )
    monkeypatch.setenv("MODEL_PROFILE_BINDINGS_JSON", '{"agent":"plain-model"}')

    settings = load_provider_settings_from_env()
    endpoint = settings.get_profile_binding("agent").endpoints[0]

    assert endpoint.thinking_effort is None


def test_endpoint_from_dict_loads_thinking_effort() -> None:
    raw = {
        "provider": "anthropic",
        "model": "claude-opus-4-6",
        "thinking_effort": "medium",
    }
    ep = _endpoint_from_dict(raw, "TEST")
    assert ep.thinking_effort == "medium"


def test_build_primary_endpoint_reads_thinking_effort_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENT_MODEL", "claude-opus-4-6")
    monkeypatch.setenv("AGENT_PROVIDER", "anthropic")
    monkeypatch.setenv("AGENT_THINKING_EFFORT", "xhigh")

    settings = load_provider_settings_from_env()
    endpoint = settings.get_profile_binding("agent").endpoints[0]

    assert endpoint.thinking_effort == "xhigh"


def test_unknown_effort_raises_at_config_load(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "MODEL_DEFINITIONS_JSON",
        '{"bad-model":{"provider":"anthropic","model":"claude-opus-4-6",'
        '"thinking_effort":"turbo"}}',
    )
    monkeypatch.setenv("MODEL_PROFILE_BINDINGS_JSON", '{"agent":"bad-model"}')

    with pytest.raises(ProviderConfigError, match="thinking_effort"):
        load_provider_settings_from_env()


# -------------------------------------------------------------------
# NativeProviderClient — budget maps
# -------------------------------------------------------------------

def test_thinking_budget_map_values() -> None:
    assert _THINKING_BUDGET_MAP["low"] == 4096
    assert _THINKING_BUDGET_MAP["medium"] == 8192
    assert _THINKING_BUDGET_MAP["high"] == 16384
    assert _THINKING_BUDGET_MAP["xhigh"] == 32768
    for effort in ("low", "medium", "high", "xhigh"):
        assert _THINKING_MAX_TOKENS_MAP[effort] > _THINKING_BUDGET_MAP[effort], (
            f"max_tokens must be > budget_tokens for effort={effort}"
        )


# -------------------------------------------------------------------
# NativeProviderClient — no injection when thinking_effort is None
# -------------------------------------------------------------------

def test_no_thinking_effort_no_injection() -> None:
    client = _make_client()
    captured: dict = {}

    mock_response = MagicMock()
    mock_response.content = []
    mock_response.usage = None
    mock_response.stop_reason = "end_turn"

    def fake_create(**kwargs):
        captured.update(kwargs)
        return mock_response

    mock_anthropic = MagicMock()
    mock_anthropic.messages.create.side_effect = fake_create

    with patch("anthropic.Anthropic", return_value=mock_anthropic):
        client._invoke_anthropic_chat(
            system_prompt="sys",
            messages=[{"role": "user", "content": "hi"}],
            tools=None,
            on_token=None,
            on_reasoning=None,
        )

    assert "thinking" not in captured
    assert captured["temperature"] == 0.0


# -------------------------------------------------------------------
# NativeProviderClient — injection: _invoke_anthropic_chat non-streaming
# -------------------------------------------------------------------

def test_thinking_effort_injects_thinking_block() -> None:
    client = _make_client(thinking_effort="high")
    captured: dict = {}

    mock_response = MagicMock()
    mock_response.content = []
    mock_response.usage = None
    mock_response.stop_reason = "end_turn"

    def fake_create(**kwargs):
        captured.update(kwargs)
        return mock_response

    mock_anthropic = MagicMock()
    mock_anthropic.messages.create.side_effect = fake_create

    with patch("anthropic.Anthropic", return_value=mock_anthropic):
        client._invoke_anthropic_chat(
            system_prompt="sys",
            messages=[{"role": "user", "content": "hi"}],
            tools=None,
            on_token=None,
            on_reasoning=None,
        )

    assert captured["thinking"] == {"type": "enabled", "budget_tokens": 16384}
    assert captured["temperature"] == 1
    assert captured["max_tokens"] == _THINKING_MAX_TOKENS_MAP["high"]


# -------------------------------------------------------------------
# NativeProviderClient — injection: _invoke_anthropic (single-turn) non-streaming
# -------------------------------------------------------------------

def test_thinking_effort_injects_thinking_block_invoke_anthropic() -> None:
    client = _make_client(thinking_effort="low")
    captured: dict = {}

    mock_response = MagicMock()
    mock_response.content = []
    mock_response.usage = None
    mock_response.stop_reason = "end_turn"

    def fake_create(**kwargs):
        captured.update(kwargs)
        return mock_response

    mock_anthropic = MagicMock()
    mock_anthropic.messages.create.side_effect = fake_create

    with patch("anthropic.Anthropic", return_value=mock_anthropic):
        client._invoke_anthropic(
            system_prompt="sys",
            body="hello",
            tools=None,
            on_token=None,
            on_reasoning=None,
        )

    assert captured["thinking"] == {"type": "enabled", "budget_tokens": 4096}
    assert captured["temperature"] == 1
    assert captured["max_tokens"] == _THINKING_MAX_TOKENS_MAP["low"]


# -------------------------------------------------------------------
# NativeProviderClient — injection: streaming path
# -------------------------------------------------------------------

def test_thinking_effort_injects_thinking_block_streaming() -> None:
    client = _make_client(thinking_effort="medium")
    captured: dict = {}

    mock_stream = MagicMock()
    mock_stream.__enter__ = lambda s: s
    mock_stream.__exit__ = MagicMock(return_value=False)
    mock_stream.__iter__ = lambda s: iter([])
    mock_stream.get_final_message.return_value = MagicMock(
        content=[], usage=None, stop_reason="end_turn"
    )

    def fake_stream(**kwargs):
        captured.update(kwargs)
        return mock_stream

    mock_anthropic = MagicMock()
    mock_anthropic.messages.stream.side_effect = fake_stream

    tokens: list[str] = []
    with patch("anthropic.Anthropic", return_value=mock_anthropic):
        client._invoke_anthropic_chat(
            system_prompt="sys",
            messages=[{"role": "user", "content": "hi"}],
            tools=None,
            on_token=tokens.append,
            on_reasoning=None,
        )

    assert captured["thinking"] == {"type": "enabled", "budget_tokens": 8192}
    assert captured["temperature"] == 1
    assert captured["max_tokens"] == _THINKING_MAX_TOKENS_MAP["medium"]


# -------------------------------------------------------------------
# NativeProviderClient — OpenAI path unaffected
# -------------------------------------------------------------------

def test_openai_call_unaffected_by_thinking_effort() -> None:
    ep = ProviderEndpoint(
        provider="openai",
        model="gpt-4o",
        api_key="test-key",
        thinking_effort="high",  # should be ignored for OpenAI
    )
    client = NativeProviderClient(ep)
    captured: dict = {}

    mock_response = MagicMock()
    mock_response.choices = [MagicMock(
        message=MagicMock(content="ok", tool_calls=None),
        finish_reason="stop",
    )]
    mock_response.usage = None

    def fake_create(**kwargs):
        captured.update(kwargs)
        return mock_response

    mock_openai = MagicMock()
    mock_openai.chat.completions.create.side_effect = fake_create

    with patch("openai.OpenAI", return_value=mock_openai):
        client._invoke_openai_chat(
            system_prompt="sys",
            messages=[{"role": "user", "content": "hi"}],
            tools=None,
            on_token=None,
        )

    assert "thinking" not in captured
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/nigelleong/Desktop/personal/teambot
.venv/bin/python -m pytest tests/test_thinking_budget.py -v 2>&1 | head -60
```
Expected: failures on `ProviderEndpoint` having no `thinking_effort` attribute, `_THINKING_BUDGET_MAP` not importable from `native`, `_parse_thinking_effort`/`ProviderConfigError` matching not working, etc. The `_endpoint_from_dict` import itself will succeed (private functions are importable in Python), but `ep.thinking_effort` will fail with `AttributeError`.

---

### Task 2: Add `thinking_effort` to `ProviderEndpoint`

**Files:**
- Modify: `src/teambot/providers/base.py:10-23`

- [ ] **Step 3: Add field and update `key` property**

Replace the current `ProviderEndpoint` dataclass (lines 10–23) with:

```python
@dataclass(frozen=True)
class ProviderEndpoint:
    provider: str
    model: str
    api_key: str | None = None
    base_url: str | None = None
    timeout_seconds: int = 20
    temperature: float = 0.0
    thinking_effort: str | None = None

    @property
    def key(self) -> str:
        return (
            f"{self.provider.lower()}::{self.model}::"
            f"{self.base_url or ''}::{self.timeout_seconds}::{self.temperature}"
            f"::{self.thinking_effort or ''}"
        )
```

- [ ] **Step 4: Run ProviderEndpoint tests**

```bash
.venv/bin/python -m pytest tests/test_thinking_budget.py::test_thinking_effort_defaults_to_none tests/test_thinking_budget.py::test_thinking_effort_stored_correctly tests/test_thinking_budget.py::test_key_includes_thinking_effort_when_set tests/test_thinking_budget.py::test_key_differs_between_effort_levels -v
```
Expected: 4 PASS

---

### Task 3: Update config loaders

**Files:**
- Modify: `src/teambot/providers/config.py` (add helper after line 25, update three loader functions)

- [ ] **Step 5: Add `_VALID_THINKING_EFFORTS` constant and `_parse_thinking_effort` helper**

After the imports block ends at line 25 (after the closing `)` of `from .registry import (...)`), and before `def load_provider_settings_from_env` at line 28, add:

```python
_VALID_THINKING_EFFORTS: frozenset[str] = frozenset({"low", "medium", "high", "xhigh"})


def _parse_thinking_effort(value: str | None, context: str) -> str | None:
    if not value:
        return None
    if value not in _VALID_THINKING_EFFORTS:
        raise ProviderConfigError(
            f"{context}: thinking_effort '{value}' is not valid. "
            f"Valid values: {', '.join(sorted(_VALID_THINKING_EFFORTS))}"
        )
    return value
```

- [ ] **Step 6: Update `_endpoint_from_config_dict` (line 338)**

In `_endpoint_from_config_dict`, before the `return ProviderEndpoint(` at line 357, add one line and update the constructor call. The full updated return block:

Old (lines 356–368):
```python
    api_key = _resolve_definition_api_key(raw=raw, provider=provider)
    base_url_raw = raw.get("base_url")
    return ProviderEndpoint(
        provider=provider,
        model=model,
        api_key=api_key,
        base_url=(
            str(base_url_raw).strip()
            if isinstance(base_url_raw, str)
            else default_base_url_for_provider(provider) or None
        ),
        timeout_seconds=timeout_seconds,
        temperature=temperature,
    )
```

New:
```python
    api_key = _resolve_definition_api_key(raw=raw, provider=provider)
    base_url_raw = raw.get("base_url")
    thinking_effort = _parse_thinking_effort(raw.get("thinking_effort") or None, env_name)
    return ProviderEndpoint(
        provider=provider,
        model=model,
        api_key=api_key,
        base_url=(
            str(base_url_raw).strip()
            if isinstance(base_url_raw, str)
            else default_base_url_for_provider(provider) or None
        ),
        timeout_seconds=timeout_seconds,
        temperature=temperature,
        thinking_effort=thinking_effort,
    )
```

- [ ] **Step 7: Update `_endpoint_from_dict` (line 447)**

In `_endpoint_from_dict`, before the `return ProviderEndpoint(` at line 469, add one line and update the constructor call.

Old (lines 467–476):
```python
    api_key_raw = raw.get("api_key")
    base_url_raw = raw.get("base_url")
    return ProviderEndpoint(
        provider=provider,
        model=model,
        api_key=str(api_key_raw).strip() if isinstance(api_key_raw, str) else None,
        base_url=str(base_url_raw).strip() if isinstance(base_url_raw, str) else None,
        timeout_seconds=timeout_seconds,
        temperature=temperature,
    )
```

New:
```python
    api_key_raw = raw.get("api_key")
    base_url_raw = raw.get("base_url")
    thinking_effort = _parse_thinking_effort(raw.get("thinking_effort") or None, env_name)
    return ProviderEndpoint(
        provider=provider,
        model=model,
        api_key=str(api_key_raw).strip() if isinstance(api_key_raw, str) else None,
        base_url=str(base_url_raw).strip() if isinstance(base_url_raw, str) else None,
        timeout_seconds=timeout_seconds,
        temperature=temperature,
        thinking_effort=thinking_effort,
    )
```

- [ ] **Step 8: Update `_build_primary_endpoint` (line 393)**

In `_build_primary_endpoint`, before the `return ProviderEndpoint(` at line 415, add two lines and update the constructor call.

Old (lines 413–421):
```python
    timeout_raw = _read_env(f"{env_prefix}_TIMEOUT_SECONDS") or "20"
    timeout_seconds = int(timeout_raw) if timeout_raw.isdigit() else 20
    return ProviderEndpoint(
        provider=provider,
        model=model,
        api_key=api_key,
        base_url=base_url,
        timeout_seconds=timeout_seconds,
    )
```

New:
```python
    timeout_raw = _read_env(f"{env_prefix}_TIMEOUT_SECONDS") or "20"
    timeout_seconds = int(timeout_raw) if timeout_raw.isdigit() else 20
    thinking_effort = _parse_thinking_effort(
        _read_env(f"{env_prefix}_THINKING_EFFORT") or None,
        f"{env_prefix}_THINKING_EFFORT",
    )
    return ProviderEndpoint(
        provider=provider,
        model=model,
        api_key=api_key,
        base_url=base_url,
        timeout_seconds=timeout_seconds,
        thinking_effort=thinking_effort,
    )
```

- [ ] **Step 9: Run config loader tests**

```bash
.venv/bin/python -m pytest tests/test_thinking_budget.py -k "config_dict or from_dict or primary or unknown" -v
```
Expected: all PASS

- [ ] **Step 10: Run full suite to check no regressions**

```bash
.venv/bin/python -m pytest tests/ -x -q 2>&1 | tail -20
```
Expected: same pass/fail ratio as before

- [ ] **Step 11: Commit**

```bash
git add src/teambot/providers/base.py src/teambot/providers/config.py tests/test_thinking_budget.py
git commit -m "feat(providers): add thinking_effort to ProviderEndpoint + config loaders"
```

---

## Chunk 2: Native client injection

### Task 4: Add budget maps and injection in native client

**Files:**
- Modify: `src/teambot/providers/clients/native.py` (after line 14, and in `_invoke_anthropic` + `_invoke_anthropic_chat`)

- [ ] **Step 1: Run native-only tests to verify they currently fail**

```bash
.venv/bin/python -m pytest tests/test_thinking_budget.py -k "map or inject or openai" -v 2>&1 | head -30
```
Expected: FAIL — `_THINKING_BUDGET_MAP` not importable, injection not implemented

- [ ] **Step 2: Add maps after `_ANTHROPIC_DEFAULT_MAX_TOKENS` (line 14)**

After `_ANTHROPIC_DEFAULT_MAX_TOKENS = 8192`, add:

```python
_THINKING_BUDGET_MAP: dict[str, int] = {
    "low":    4096,
    "medium": 8192,
    "high":   16384,
    "xhigh":  32768,
}

_THINKING_MAX_TOKENS_MAP: dict[str, int] = {
    "low":    8192,
    "medium": 12288,
    "high":   20480,
    "xhigh":  36864,
}
```

- [ ] **Step 3: Inject in `_invoke_anthropic` (line 273)**

In `_invoke_anthropic`, after the `if tools:` block (which ends at line 292) and before `if on_token is not None or on_reasoning is not None:` (line 294), add:

Old (lines 290–295):
```python
        if tools:
            params["tools"] = [_anthropic_tool_spec(t) for t in tools]
            params["tool_choice"] = {"type": "auto"}

        if on_token is not None or on_reasoning is not None:
```

New:
```python
        if tools:
            params["tools"] = [_anthropic_tool_spec(t) for t in tools]
            params["tool_choice"] = {"type": "auto"}

        if self.endpoint.thinking_effort:
            budget = _THINKING_BUDGET_MAP[self.endpoint.thinking_effort]
            params["thinking"] = {"type": "enabled", "budget_tokens": budget}
            params["temperature"] = 1
            params["max_tokens"] = _THINKING_MAX_TOKENS_MAP[self.endpoint.thinking_effort]

        if on_token is not None or on_reasoning is not None:
```

- [ ] **Step 4: Inject in `_invoke_anthropic_chat` (line 304)**

In `_invoke_anthropic_chat`, after the `if tools:` block (which ends at line 323) and before `if on_token is not None or on_reasoning is not None:` (line 325), add the same block:

Old (lines 321–326):
```python
        if tools:
            params["tools"] = [_anthropic_tool_spec(t) for t in tools]
            params["tool_choice"] = {"type": "auto"}

        if on_token is not None or on_reasoning is not None:
```

New:
```python
        if tools:
            params["tools"] = [_anthropic_tool_spec(t) for t in tools]
            params["tool_choice"] = {"type": "auto"}

        if self.endpoint.thinking_effort:
            budget = _THINKING_BUDGET_MAP[self.endpoint.thinking_effort]
            params["thinking"] = {"type": "enabled", "budget_tokens": budget}
            params["temperature"] = 1
            params["max_tokens"] = _THINKING_MAX_TOKENS_MAP[self.endpoint.thinking_effort]

        if on_token is not None or on_reasoning is not None:
```

- [ ] **Step 5: Run all thinking budget tests**

```bash
.venv/bin/python -m pytest tests/test_thinking_budget.py -v
```
Expected: all PASS

- [ ] **Step 6: Run full test suite**

```bash
.venv/bin/python -m pytest tests/ -x -q 2>&1 | tail -20
```
Expected: same pass/fail ratio as before

- [ ] **Step 7: Commit**

```bash
git add src/teambot/providers/clients/native.py
git commit -m "feat(native): inject Anthropic thinking block from thinking_effort endpoint field"
```

---

## Final check

- [ ] **Verify the feature end-to-end with a dry-run env test**

```bash
AGENT_MODEL=claude-opus-4-6 AGENT_PROVIDER=anthropic AGENT_THINKING_EFFORT=high \
  .venv/bin/python -c "
from teambot.providers.config import load_provider_settings_from_env
s = load_provider_settings_from_env()
ep = s.get_profile_binding('agent').endpoints[0]
print('thinking_effort:', ep.thinking_effort)
print('key:', ep.key)
"
```
Expected output:
```
thinking_effort: high
key: anthropic::claude-opus-4-6::::20::0.0::high
```

No changes to `config/config.json` are required — the field is opt-in. Omitting it means no extended thinking.
