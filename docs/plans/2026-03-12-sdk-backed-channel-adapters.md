# SDK-Backed Channel Adapters Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the current hand-written Slack, Telegram, Discord, WhatsApp, and Feishu ingress parsers with mature SDK-backed adapter implementations while preserving the existing TeamBot gateway boundary.

**Architecture:** Keep FastAPI routes, `GatewayManager`, `ChannelAdapter`, and `ChannelEnvelope` as the stable integration seam. Replace only the concrete channel plugin internals so each adapter delegates verification and payload modeling to the most mature available SDK, then maps the resulting event into `ChannelEnvelope`.

**Tech Stack:** FastAPI, Pydantic, pytest, `slack-bolt`, `python-telegram-bot`, `pywa`, `larksuite/oapi-sdk-python`, one Discord interaction/webhook library selected during implementation

---

### Task 1: Freeze current ingress behavior with tests

**Files:**
- Modify: `tests/test_gateway_ingress.py`

**Step 1: Write the failing or tightened tests**

Add or tighten assertions so the current ingress contract is explicit:

- Slack URL verification returns challenge
- Slack event callback maps to the expected reply and normalized fields
- Telegram webhook update maps to the expected reply and normalized fields
- Discord interaction ping / application command behavior remains explicit
- WhatsApp text message webhook maps to the expected reply and normalized fields
- Feishu URL verification and message callback remain explicit
- `/gateway/channels` stays unexposed and returns `404`

**Step 2: Run test to verify current baseline**

Run: `PYTHONPATH=src .venv310/bin/python -m pytest -q tests/test_gateway_ingress.py`

Expected: PASS, establishing the public ingress contract before adapter replacement.

**Step 3: Commit**

```bash
git add tests/test_gateway_ingress.py
git commit -m "test: lock gateway ingress contract before sdk migration"
```

### Task 2: Add SDK dependencies and env keys

**Files:**
- Modify: `requirements.txt`
- Modify: `requirements-dev.txt` if test-only helpers are required
- Modify: `/Users/nigelleong/Desktop/personal/langgraph-teambot-mvp/.env.template`
- Modify: `docs/README.md`
- Modify: `docs/code-structure.md`
- Modify: `repo_wiki.md`

**Step 1: Add the new runtime dependencies**

Add:

- `slack-bolt`
- `python-telegram-bot`
- `pywa`
- the correct pip package for the Lark/Feishu SDK
- the selected Discord interactions library

Do not add any dependency whose exact package name has not been verified from official docs.

**Step 2: Add or document env keys**

Document any required keys in `.env.template`, for example:

- Slack signing secret / bot token
- Telegram bot token / secret token
- WhatsApp verify token / app secret / access token if required
- Feishu app credentials or callback secret material
- Discord public key if the selected interaction library requires it

**Step 3: Run a dependency smoke check**

Run:

```bash
.venv310/bin/python - <<'PY'
import importlib
for name in [
    "slack_bolt",
    "telegram",
]:
    importlib.import_module(name)
print("ok")
PY
```

Expected: imports succeed for installed packages. Extend the smoke check once exact WhatsApp, Feishu, and Discord module names are confirmed.

**Step 4: Commit**

```bash
git add requirements.txt requirements-dev.txt /Users/nigelleong/Desktop/personal/langgraph-teambot-mvp/.env.template docs/README.md docs/code-structure.md repo_wiki.md
git commit -m "chore: add sdk dependencies for channel adapters"
```

### Task 3: Migrate Slack adapter to `slack-bolt`

**Files:**
- Modify: `src/teambot/channels/plugins/slack.py`
- Modify: `src/teambot/channels/registry.py` if registration shape changes
- Modify: `tests/test_gateway_ingress.py`

**Step 1: Write the failing Slack-specific test**

Add a test for invalid Slack signature or missing Slack verification material once the SDK-backed path is in place.

**Step 2: Run the Slack-focused test**

Run: `PYTHONPATH=src .venv310/bin/python -m pytest -q tests/test_gateway_ingress.py -k slack`

Expected: FAIL before implementation.

**Step 3: Replace the Slack adapter internals**

Implement:

- SDK-backed request verification
- SDK-backed event/request parsing
- mapping of supported Slack message events into `ChannelEnvelope`
- preservation of URL verification behavior

Do not change gateway route shapes.

**Step 4: Re-run Slack tests**

Run: `PYTHONPATH=src .venv310/bin/python -m pytest -q tests/test_gateway_ingress.py -k slack`

Expected: PASS.

**Step 5: Commit**

```bash
git add src/teambot/channels/plugins/slack.py src/teambot/channels/registry.py tests/test_gateway_ingress.py
git commit -m "feat: migrate slack ingress adapter to bolt"
```

### Task 4: Migrate WhatsApp adapter to `pywa`

**Files:**
- Modify: `src/teambot/channels/plugins/whatsapp.py`
- Modify: `tests/test_gateway_ingress.py`
- Modify: `/Users/nigelleong/Desktop/personal/langgraph-teambot-mvp/.env.template`

**Step 1: Write the failing WhatsApp-focused tests**

Add tests for:

- webhook verification challenge
- valid text message webhook
- invalid verification token or invalid signature behavior if supported by the chosen integration path

**Step 2: Run the WhatsApp-focused tests**

Run: `PYTHONPATH=src .venv310/bin/python -m pytest -q tests/test_gateway_ingress.py -k whatsapp`

Expected: FAIL before implementation.

**Step 3: Replace the WhatsApp adapter internals**

Use `pywa` parsing / webhook verification primitives and map supported text messages into `ChannelEnvelope`.

**Step 4: Re-run WhatsApp tests**

Run: `PYTHONPATH=src .venv310/bin/python -m pytest -q tests/test_gateway_ingress.py -k whatsapp`

Expected: PASS.

**Step 5: Commit**

```bash
git add src/teambot/channels/plugins/whatsapp.py tests/test_gateway_ingress.py /Users/nigelleong/Desktop/personal/langgraph-teambot-mvp/.env.template
git commit -m "feat: migrate whatsapp ingress adapter to pywa"
```

### Task 5: Migrate Telegram adapter to `python-telegram-bot`

**Files:**
- Modify: `src/teambot/channels/plugins/telegram.py`
- Modify: `tests/test_gateway_ingress.py`
- Modify: `/Users/nigelleong/Desktop/personal/langgraph-teambot-mvp/.env.template`

**Step 1: Write the failing Telegram-focused tests**

Add tests for:

- webhook secret token validation when configured
- text message update normalization
- ignored non-message updates

**Step 2: Run the Telegram-focused tests**

Run: `PYTHONPATH=src .venv310/bin/python -m pytest -q tests/test_gateway_ingress.py -k telegram`

Expected: FAIL before implementation.

**Step 3: Replace the Telegram adapter internals**

Use `python-telegram-bot` update modeling / webhook semantics and map supported text messages into `ChannelEnvelope`.

**Step 4: Re-run Telegram tests**

Run: `PYTHONPATH=src .venv310/bin/python -m pytest -q tests/test_gateway_ingress.py -k telegram`

Expected: PASS.

**Step 5: Commit**

```bash
git add src/teambot/channels/plugins/telegram.py tests/test_gateway_ingress.py /Users/nigelleong/Desktop/personal/langgraph-teambot-mvp/.env.template
git commit -m "feat: migrate telegram ingress adapter to python-telegram-bot"
```

### Task 6: Migrate Feishu adapter to the Lark SDK

**Files:**
- Modify: `src/teambot/channels/plugins/feishu.py`
- Modify: `tests/test_gateway_ingress.py`
- Modify: `/Users/nigelleong/Desktop/personal/langgraph-teambot-mvp/.env.template`

**Step 1: Write the failing Feishu-focused tests**

Add tests for:

- URL verification
- signed callback validation when configured
- `im.message.receive_v1` text normalization

**Step 2: Run the Feishu-focused tests**

Run: `PYTHONPATH=src .venv310/bin/python -m pytest -q tests/test_gateway_ingress.py -k feishu`

Expected: FAIL before implementation.

**Step 3: Replace the Feishu adapter internals**

Use the Lark SDK callback utilities for verification / decoding and map supported text message events into `ChannelEnvelope`.

**Step 4: Re-run Feishu tests**

Run: `PYTHONPATH=src .venv310/bin/python -m pytest -q tests/test_gateway_ingress.py -k feishu`

Expected: PASS.

**Step 5: Commit**

```bash
git add src/teambot/channels/plugins/feishu.py tests/test_gateway_ingress.py /Users/nigelleong/Desktop/personal/langgraph-teambot-mvp/.env.template
git commit -m "feat: migrate feishu ingress adapter to lark sdk"
```

### Task 7: Migrate Discord adapter to a mature interactions library

**Files:**
- Modify: `src/teambot/channels/plugins/discord.py`
- Modify: `tests/test_gateway_ingress.py`
- Modify: `/Users/nigelleong/Desktop/personal/langgraph-teambot-mvp/.env.template`

**Step 1: Confirm the library selection in code comments or docs**

Before implementation, document which Discord library was selected and why it was preferred over full bot frameworks.

**Step 2: Write the failing Discord-focused tests**

Add tests for:

- Ed25519 signature verification failure behavior
- valid PING interaction
- valid application command normalization into `ChannelEnvelope`

**Step 3: Run the Discord-focused tests**

Run: `PYTHONPATH=src .venv310/bin/python -m pytest -q tests/test_gateway_ingress.py -k discord`

Expected: FAIL before implementation.

**Step 4: Replace the Discord adapter internals**

Use the selected interactions library for verification and typed interaction parsing. Keep scope limited to ingress-only HTTP interactions.

**Step 5: Re-run Discord tests**

Run: `PYTHONPATH=src .venv310/bin/python -m pytest -q tests/test_gateway_ingress.py -k discord`

Expected: PASS.

**Step 6: Commit**

```bash
git add src/teambot/channels/plugins/discord.py tests/test_gateway_ingress.py /Users/nigelleong/Desktop/personal/langgraph-teambot-mvp/.env.template
git commit -m "feat: migrate discord ingress adapter to interactions sdk"
```

### Task 8: Full verification and docs sync

**Files:**
- Modify: `README.md`
- Modify: `docs/modules/api-and-debug.md`
- Modify: `docs/README.md`
- Modify: `docs/code-structure.md`
- Modify: `repo_wiki.md`

**Step 1: Update docs**

Document:

- SDK-backed adapter architecture
- channel-specific env requirements
- unchanged public ingress routes
- current scope remains ingress-only

**Step 2: Run full relevant verification**

Run:

```bash
PYTHONPATH=src .venv310/bin/python -m pytest -q tests/test_gateway_ingress.py tests/test_interface_parity.py
PYTHONPATH=src .venv310/bin/python -m pytest -q tests/test_runtime_events.py tests/test_routing.py
```

Expected: PASS.

**Step 3: Commit**

```bash
git add README.md docs/modules/api-and-debug.md docs/README.md docs/code-structure.md repo_wiki.md
git commit -m "docs: describe sdk-backed gateway adapters"
```
