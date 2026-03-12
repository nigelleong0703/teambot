# Browser And Web Fetch Split Design

## 1. Context

TeamBot currently exposes `browser_use`, but the implementation is only a shallow HTTP fetch. That creates a naming and behavior mismatch:

- the current tool is useful for URL retrieval
- the current tool is not a real browser automation surface
- docs already call out the gap against an OpenClaw-style `browser(action=...)` protocol

We will split these concerns into two separate tools instead of overloading one tool with both behaviors.

## 2. Decision

Introduce two distinct tools:

1. `web_fetch`
   - narrow, stateless URL retrieval
   - intended for reading or extracting content from an explicit URL
2. `browser`
   - stateful browser automation surface
   - intended for interactive page workflows

The existing `browser_use` name should be retired from the primary runtime surface once compatibility concerns are handled.

## 3. Tool Semantics

### 3.1 `web_fetch`

Purpose:
- fetch content from a specific URL for reading or extraction

Core properties:
- stateless
- no tab/session management
- no click/type/screenshot behavior
- optimized for low-latency retrieval

Initial schema:
- `url` (required)
- `timeout_seconds` (optional)
- `max_chars` (optional)

Initial return shape:
- `final_url`
- `status_code`
- `content_type`
- `content`
- optional error flags/messages on failure

### 3.2 `browser`

Purpose:
- control a real browser for rendered-page observation and UI interaction

Initial action scope:
- `open`
- `tabs`
- `snapshot`
- `act`
- `screenshot`
- `close`

Initial `act` kinds:
- `click`
- `type`
- `press`
- `hover`
- `wait`

This first version should align the request shape with the OpenClaw direction (`browser(action=...)`) without importing the whole OpenClaw browser stack.

## 4. Default Routing Rule

The default preference should be expressed in tool descriptions:

- prefer `web_fetch` when the user provides a URL and only content retrieval/reading is needed
- use `browser` only when interaction, rendered-page inspection, screenshots, or browser state are required

This rule belongs first in tool descriptions. If model behavior still drifts, we can reinforce it in the reasoner prompt later.

## 5. OpenClaw Alignment Boundary

We should align to OpenClaw at the protocol boundary, not by copying its entire runtime:

- adopt the `browser(action=...)` shape
- keep action names close to OpenClaw where practical
- keep the TeamBot implementation minimal in phase one

Out of scope for the first TeamBot pass:
- browser profiles
- host/sandbox/node targeting
- PDF export
- upload/file chooser hooks
- dialog hooks
- remote browser proxying

## 6. Rollout Plan

Phase 1:
- add `web_fetch`
- add minimal `browser`
- update tool registry/profile wiring
- update tests and runtime docs

Phase 2:
- consider richer browser actions or closer OpenClaw parity if the minimal surface proves stable

## 7. Risks

- model may continue preferring the wrong tool if descriptions are vague
- browser naming without enough action support can still create expectation gaps
- keeping `browser_use` alive too long can confuse tests and docs

## 8. Success Criteria

- TeamBot exposes separate `web_fetch` and `browser` tools
- `web_fetch` clearly replaces the old shallow fetch semantics
- `browser` is reserved for genuine interactive workflows
- docs and tests describe the split consistently
