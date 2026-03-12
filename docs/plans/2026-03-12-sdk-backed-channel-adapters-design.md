# SDK-Backed Channel Adapters Design

**Date:** 2026-03-12

## Goal

Replace the current hand-written ingress parsers for `slack`, `telegram`, `discord`, `whatsapp`, and `feishu` with mature SDK-backed implementations while preserving the existing TeamBot gateway boundary:

`HTTP route -> channel adapter -> ChannelEnvelope -> InboundEvent -> AgentService`

## Problem

The current gateway ingress layer is structurally correct but too custom. Each channel plugin manually parses payloads and manually encodes platform-specific assumptions. That creates three problems:

1. Signature verification and webhook protocol details are easy to get wrong.
2. Event shape drift across platform API versions will become our maintenance burden.
3. The repo violates its own "reuse before build" policy when mature SDKs already exist.

## Constraints

- Keep the current ingress-only scope. Do not reintroduce control-plane APIs.
- Preserve the existing FastAPI routes:
  - `POST /events/slack`
  - `POST /events/{channel}`
  - `POST /gateway/{channel}/events`
- Preserve the current `ChannelEnvelope -> InboundEvent` dispatch boundary so Agent Core remains channel-agnostic.
- Keep diffs task-scoped and additive where possible.
- Update `/Users/nigelleong/Desktop/personal/langgraph-teambot-mvp/.env.template` whenever env keys change.
- Update docs in the same change when behavior changes.

## Non-Goals

- No outbound delivery work.
- No channel lifecycle/control-plane work.
- No start/stop/reload/status APIs.
- No attempt to unify each SDK's full runtime model inside Agent Core.

## Design Summary

Retain the current gateway orchestration and standardized envelope model, but replace the internal implementation of each channel adapter with the most mature available SDK or ecosystem-standard library.

The TeamBot adapter remains the compatibility layer between each SDK and our internal runtime. SDKs own:

- request verification
- protocol-specific request parsing
- event/update object modeling
- challenge / handshake flows

TeamBot owns:

- route registration
- adapter lookup
- conversion into `ChannelEnvelope`
- mapping into existing `InboundEvent`
- dispatch into `AgentService`

## Selected SDK Direction

### Slack

Use `slack-bolt`.

Reasoning:

- official SDK
- built-in request verification
- built-in FastAPI adapter support
- matches how `openclaw` delegates HTTP verification to Slack Bolt / receiver infrastructure rather than hand-rolling verification in gateway code

Planned adapter shape:

- instantiate Slack Bolt app / handler once
- use SDK verification path for incoming requests
- map supported message events into `ChannelEnvelope`
- preserve `url_verification` behavior through SDK handling or equivalent official request path

### Telegram

Use `python-telegram-bot` with custom webhook integration.

Reasoning:

- dominant Python SDK for Telegram bots
- supports webhook-driven integrations
- supports webhook secret token flow
- provides typed `Update` modeling that is preferable to manual JSON extraction

Planned adapter shape:

- parse incoming webhook body into SDK update objects
- validate secret token header when configured
- map message updates into `ChannelEnvelope`
- keep ingress scope limited to textual message updates

### WhatsApp

Use `pywa`.

Reasoning:

- Python-first WhatsApp Cloud API integration
- explicit FastAPI support
- built-in webhook verification flow
- substantially better than maintaining our own Meta webhook parser

Planned adapter shape:

- use `pywa` request parsing / webhook verification primitives
- support challenge / verify-token handshake
- map inbound text messages into `ChannelEnvelope`

### Feishu

Use `larksuite/oapi-sdk-python`.

Reasoning:

- official/officially maintained ecosystem SDK
- explicit support for event subscriptions and callback handling
- includes signing / encryption utilities rather than requiring custom webhook parsing

Planned adapter shape:

- use SDK helpers for callback validation / decoding
- handle `url_verification`
- map `im.message.receive_v1` text events into `ChannelEnvelope`

### Discord

Use a mature interaction/webhook-focused Python library rather than a full bot runtime.

Reasoning:

- Discord does not provide an official SDK
- current scope is ingress-only, not gateway websocket runtime
- a thin interactions library is a better fit than adopting a full Discord client runtime prematurely

Selection rule:

- choose a library that supports Ed25519 request verification and typed interaction parsing
- avoid adopting a full gateway bot framework unless later runtime requirements justify it

## Architecture

### Stable internal interfaces

These should remain:

- `src/teambot/channels/base.py`
- `src/teambot/channels/models.py`
- `src/teambot/channels/registry.py`
- `src/teambot/gateway/manager.py`
- `src/teambot/gateway/dispatch.py`
- `src/teambot/app/main.py`

### What changes

The concrete plugin files under `src/teambot/channels/plugins/` stop being "manual JSON parsers" and become "SDK-backed mappers".

In practice that means:

- `verify_request()` uses SDK-native verification where available
- `parse_request()` uses SDK-native decoding / modeling where available
- `resolve_immediate_response()` handles handshake/challenge flows through SDK or official protocol semantics
- `normalize_event()` converts SDK objects into `ChannelEnvelope`

### Why keep `ChannelEnvelope`

Without `ChannelEnvelope`, the SDKs would leak directly into Agent Core. That would make runtime behavior channel-specific and significantly harder to test. The envelope remains the correct seam:

- SDKs terminate at the channel adapter boundary
- Agent Core still sees one standard event model
- test coverage can focus on normalized behavior instead of every SDK type leaking through the stack

## Error Handling

- Unknown channels remain `404`.
- Malformed payloads remain `422` where applicable.
- Signature verification failures should return channel-appropriate `401` or `403` behavior.
- Unsupported but valid event types should return ack/ignore behavior, not hard failures.

## Migration Strategy

Do not replace all five adapters at once in one commit.

Use this sequence:

1. Slack
2. WhatsApp
3. Telegram
4. Feishu
5. Discord

For each channel:

1. add dependency
2. add failing tests
3. replace adapter internals
4. update env template
5. update docs
6. verify tests

This keeps regressions isolated and makes rollback straightforward.

## Rollback

Rollback remains simple because the gateway boundary does not change.

If a channel SDK integration proves unstable:

- revert only that channel adapter and its dependency entry
- keep the rest of the gateway and other adapters unchanged

## Testing Strategy

Per channel, add or update ingress tests to cover:

- valid request path
- handshake / challenge behavior if applicable
- invalid signature / invalid token behavior where applicable
- message normalization into the expected `InboundEvent`
- ignored non-message events

Retain existing gateway route tests so the public ingress API does not drift while adapters are swapped.
