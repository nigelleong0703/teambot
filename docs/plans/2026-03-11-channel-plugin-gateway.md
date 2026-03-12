# Channel Plugin Gateway Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add an OpenClaw-inspired channel-plugin gateway skeleton so TeamBot can accept HTTP message ingress from Slack, Telegram, Discord, WhatsApp, and Feishu through a shared normalization boundary.

**Architecture:** Introduce a lightweight `channels` registry/adapter layer and a lightweight `gateway` manager/dispatch layer. Keep `AgentService` unchanged as the downstream runtime and bridge the new channel-neutral envelope into the existing `InboundEvent` model.

**Tech Stack:** Python 3.11, FastAPI, Pydantic v2, pytest

---

### Task 1: Add failing tests for the new gateway boundary

**Files:**
- Create: `tests/test_gateway_ingress.py`
- Test: `tests/test_gateway_ingress.py`

**Step 1: Write the failing tests**

Add tests that assert:
- the channel registry exposes `whatsapp`, `slack`, `telegram`, `discord`, and `feishu`
- a normalized channel envelope maps deterministically into `InboundEvent`
- `/gateway/slack/events` and `/events/slack` both dispatch through the shared path
- a non-slack channel such as `/gateway/telegram/events` also dispatches

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_gateway_ingress.py`

Expected: FAIL because the gateway/channels modules and routes do not exist yet.

**Step 3: Write minimal implementation**

Create the smallest gateway/channels skeleton required to satisfy the tests.

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_gateway_ingress.py`

Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_gateway_ingress.py src/teambot/gateway src/teambot/channels src/teambot/app/main.py
git commit -m "feat: add channel plugin gateway ingress skeleton"
```

### Task 2: Implement channel-neutral envelope and adapter contracts

**Files:**
- Create: `src/teambot/channels/base.py`
- Create: `src/teambot/channels/models.py`
- Create: `src/teambot/channels/registry.py`
- Create: `src/teambot/channels/__init__.py`
- Create: `src/teambot/channels/plugins/__init__.py`
- Test: `tests/test_gateway_ingress.py`

**Step 1: Write the failing test**

Extend tests to assert:
- `ChannelEnvelope` accepts the required neutral fields
- each registered channel exposes an adapter with a stable channel id
- ignored/unsupported payloads normalize to no-op instead of crashing

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_gateway_ingress.py`

Expected: FAIL because the new contracts are incomplete.

**Step 3: Write minimal implementation**

Implement:
- `RawChannelEvent`
- `ChannelEnvelope`
- verification result model
- a simple adapter protocol
- a registry-backed set of five HTTP message adapters

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_gateway_ingress.py`

Expected: PASS

**Step 5: Commit**

```bash
git add src/teambot/channels tests/test_gateway_ingress.py
git commit -m "feat: add channel adapter and envelope contracts"
```

### Task 3: Implement gateway manager and FastAPI integration

**Files:**
- Create: `src/teambot/gateway/models.py`
- Create: `src/teambot/gateway/dispatch.py`
- Create: `src/teambot/gateway/manager.py`
- Modify: `src/teambot/app/main.py`
- Test: `tests/test_gateway_ingress.py`

**Step 1: Write the failing test**

Add assertions that:
- unknown channels return 404
- invalid payloads return 422
- successful dispatch returns reply payloads from `AgentService`

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_gateway_ingress.py`

Expected: FAIL because the HTTP dispatch flow is incomplete.

**Step 3: Write minimal implementation**

Implement:
- gateway response model
- envelope-to-`InboundEvent` mapper
- manager-driven request handling
- shared generic routes plus Slack compatibility route

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_gateway_ingress.py`

Expected: PASS

**Step 5: Commit**

```bash
git add src/teambot/gateway src/teambot/app/main.py tests/test_gateway_ingress.py
git commit -m "feat: route multi-channel ingress through gateway manager"
```

### Task 4: Update canonical docs and verify regressions

**Files:**
- Modify: `README.md`
- Modify: `docs/README.md`
- Modify: `docs/code-structure.md`
- Modify: `docs/modules/api-and-debug.md`
- Modify: `repo_wiki.md`
- Test: `tests/test_gateway_ingress.py`
- Test: `tests/test_interface_parity.py`

**Step 1: Write the doc updates**

Document:
- new `gateway/` and `channels/` packages
- supported ingress routes
- phase-1 scope and limitations

**Step 2: Run focused verification**

Run:

```bash
PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_gateway_ingress.py tests/test_interface_parity.py
```

Expected: PASS

**Step 3: Run a broader regression slice**

Run:

```bash
PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_runtime_events.py tests/test_routing.py
```

Expected: PASS

**Step 4: Commit**

```bash
git add README.md docs/README.md docs/code-structure.md docs/modules/api-and-debug.md repo_wiki.md tests/test_gateway_ingress.py src/teambot/gateway src/teambot/channels src/teambot/app/main.py
git commit -m "docs: describe channel plugin gateway ingress"
```

### Task 5: Progressively replace generic adapters with real channel payload normalizers

**Files:**
- Modify: `tests/test_gateway_ingress.py`
- Create: `src/teambot/channels/plugins/telegram.py`
- Modify: `src/teambot/channels/registry.py`
- Modify: `docs/modules/api-and-debug.md`
- Modify: `repo_wiki.md`

**Step 1: Write the failing test**

Add tests that assert:
- Slack accepts `url_verification` and `event_callback`
- Feishu accepts `url_verification` and `im.message.receive_v1`
- Telegram accepts a real webhook `update` payload with `message`

**Step 2: Run test to verify it fails**

Run:

```bash
PYTHONPATH=src .venv310/bin/python -m pytest -q tests/test_gateway_ingress.py
```

Expected: FAIL because the generic adapters do not yet understand real platform payloads.

**Step 3: Write minimal implementation**

Implement per-channel adapters for the next supported real payload shapes while keeping the generic adapter for channels that are still placeholders.

**Step 4: Run test to verify it passes**

Run:

```bash
PYTHONPATH=src .venv310/bin/python -m pytest -q tests/test_gateway_ingress.py
```

Expected: PASS

**Step 5: Update docs**

Document which channels now support platform-shaped payloads and which still use the generic message adapter.
