# Channel Plugin Gateway Design

## 1. Context

TeamBot currently exposes a single Slack-shaped ingress endpoint in `src/teambot/app/main.py`.
That path sends `InboundEvent` directly into `AgentService`, which is sufficient for the MVP CLI/TUI flow but does not provide a stable boundary for future multi-channel ingress.

The target direction is OpenClaw-like:
- `gateway` owns routing and dispatch orchestration.
- `channels` own platform-specific request verification, parsing, and normalization.
- the agent runtime remains channel-agnostic and consumes a stable internal event contract.

## 2. Scope

### In Scope
- Introduce a lightweight `channels` package with registry + adapter boundary.
- Introduce a lightweight `gateway` package for HTTP ingress dispatch.
- Support these channel IDs in the registry:
  - `whatsapp`
  - `slack`
  - `telegram`
  - `discord`
  - `feishu`
- Add a normalized gateway envelope between channel parsing and `InboundEvent`.
- Support HTTP ingress for message events only.
- Keep the current `AgentService` API as the downstream execution engine.
- Preserve `/events/slack` while also supporting a generic route family.

### Out of Scope
- Real outbound delivery back to each platform.
- Socket-mode, polling, or gateway websocket runtimes.
- Multi-account runtime lifecycle management.
- Reactions, slash commands, interactive callbacks, attachments, and media ingestion.
- Replacing the agent core event model in this change.

## 3. Design Principles

1. Standardize the boundary, not the transport.
- Different channels may ultimately use different connection styles.
- The system should unify channel ingress at the adapter contract, not force identical platform behavior.

2. Keep agent core isolated from channel details.
- `AgentService` should not know Slack, Telegram, Discord, WhatsApp, or Feishu payload structure.
- Channel details stay in channel adapters and the gateway envelope.

3. Keep the first contract intentionally small.
- Phase 1 needs only message ingress.
- Leave extension points for richer channel behavior without implementing them yet.

4. Preserve raw payloads.
- Normalization should not erase platform details needed for debugging or future features.

## 4. Target Architecture

### 4.1 New Modules

```text
src/teambot/
  gateway/
    dispatch.py
    manager.py
    models.py
  channels/
    __init__.py
    base.py
    models.py
    registry.py
    plugins/
      __init__.py
```

Platform adapters will initially live in `channels/registry.py` as lightweight HTTP adapters for message ingress only. If per-channel logic grows, they can be split into `channels/plugins/<channel>.py` without changing the external gateway boundary.

### 4.2 Contracts

#### Channel adapter contract
- `verify_request(request, body) -> ChannelVerificationResult`
- `parse_request(request, body) -> list[RawChannelEvent]`
- `normalize_event(raw_event) -> ChannelEnvelope | None`

#### Gateway manager contract
- resolve channel adapter by route/channel id
- run verify -> parse -> normalize pipeline
- map `ChannelEnvelope` into existing `InboundEvent`
- call `AgentService.process_event(...)`

### 4.3 Data Models

#### RawChannelEvent
Internal wrapper for original platform input:
- `channel`
- `headers`
- `body`
- `payload`

#### ChannelEnvelope
Neutral gateway event:
- `channel`
- `event_type`
- `event_id`
- `account_id`
- `sender_id`
- `conversation_id`
- `message_id`
- `thread_id`
- `text`
- `received_at`
- `metadata`
- `raw`

#### InboundEvent
Existing agent-core model remains unchanged in phase 1.
Gateway maps:
- `team_id <- metadata.workspace_id | metadata.team_id | channel`
- `channel_id <- conversation_id`
- `thread_ts <- thread_id | conversation_id`
- `user_id <- sender_id`

This preserves current runtime compatibility while introducing a channel-neutral ingress layer.

## 5. Routing Design

Phase 1 supports both:
- `/gateway/{channel}/events`
- `/events/{channel}`

Legacy `/events/slack` stays valid.

The handler path is unified:
1. FastAPI receives request.
2. Gateway manager resolves adapter.
3. Adapter verifies request.
4. Adapter parses request into raw channel events.
5. Adapter normalizes message events into `ChannelEnvelope`.
6. Gateway maps envelope to `InboundEvent`.
7. `AgentService.process_event(...)` runs.

The HTTP response stays gateway-local and does not attempt real platform reply delivery in this change.

## 6. Channel Handling in Phase 1

All five channels register adapters now, but only message ingress is normalized.

- Slack
  - accept direct JSON payloads shaped for TeamBot tests and manual webhook simulation
  - preserve `/events/slack`

- Telegram
  - accept JSON payloads with a top-level message-style shape

- Discord
  - accept JSON payloads with a message-style shape

- WhatsApp
  - accept JSON payloads with a message-style shape

- Feishu
  - accept JSON payloads with a message-style shape

For phase 1, adapters are intentionally lightweight and permissive. Real signature verification and provider-native payload parsing can be layered in later without changing the gateway surface.

## 7. Error Handling

- Unknown channel:
  - return HTTP 404

- Verification failure:
  - return HTTP 401

- Invalid payload:
  - return HTTP 422

- Non-message or ignored event:
  - return HTTP 202 with zero dispatched events

- Successful dispatch:
  - return HTTP 200 with normalized event count and reply payloads

## 8. Testing Strategy

### Unit
- registry resolves all five channels
- envelope-to-`InboundEvent` mapping is deterministic
- adapters normalize message payloads into `ChannelEnvelope`

### Integration
- `/gateway/{channel}/events` dispatches through the shared gateway manager
- `/events/slack` remains functional
- ignored events return accepted/no-op responses

### Regression
- existing agent runtime tests remain unchanged
- current `InboundEvent` validation remains authoritative downstream

## 9. Migration and Rollback

### Migration
1. Add gateway/channels packages and tests.
2. Rewire FastAPI ingress through gateway manager.
3. Preserve legacy Slack path for compatibility.
4. Update docs for the new ingress shape.

### Rollback
- Remove gateway/channels modules.
- Restore the direct `/events/slack -> AgentService.process_event` handler in `app/main.py`.
- No core runtime rollback is required because `AgentService` is unchanged.

## 10. Success Criteria

- TeamBot exposes a plugin-style multi-channel ingress skeleton.
- Five channels are registered behind a shared gateway boundary.
- `AgentService` still receives standard `InboundEvent` objects.
- Legacy Slack path still works.
- Docs and tests describe the new ingress architecture accurately.

## 11. Phase Roadmap

### Phase 1: Ingress Spine
- establish `gateway` + `channels` boundaries
- register five channels
- normalize inbound HTTP message events into `ChannelEnvelope`
- bridge into existing `InboundEvent`

### Phase 2: Real Per-Channel Adapters
- replace permissive generic payloads with platform-shaped parsers
- add platform-specific verification and challenge flows
- progressively support real webhook/event callback payloads per channel

### Phase 3: Gateway Control Plane
- add channel/account runtime status
- add start/stop/reload lifecycle hooks
- add health checks, reconnect/backoff, and configuration inspection
- support non-HTTP runtime transports such as socket mode, polling, or gateway/ws where needed

The intended end-state is:
- `channels` own platform implementations
- `gateway` owns control-plane orchestration and ingress dispatch
- `agent` remains runtime- and channel-agnostic
