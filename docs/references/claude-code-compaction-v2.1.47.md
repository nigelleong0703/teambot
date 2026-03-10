# Claude Code Conversation Compaction (v2.1.47)

This document records a local reverse-engineering pass over how Claude Code v2.1.47 compacts long conversations into "continued session" summary messages.

Sources used:
- Local binary: `~/.local/share/claude/versions/2.1.47`
- String extraction: `/tmp/claude-code-2.1.47.strings`
- Real local transcripts under `~/.claude/projects/...`
- Real local debug logs under `~/.claude/debug/...`

Extraction method:

```bash
strings ~/.local/share/claude/versions/2.1.47 > /tmp/claude-code-2.1.47.strings
```

Important limits:
- This is a reconstruction from the installed binary and local runtime artifacts, not from an official source release.
- Symbol names are only as reliable as what survived bundling and string extraction.
- The recovered compaction prompts are high-confidence because their text appears verbatim in the binary string table.

## High-Level Conclusion

Claude Code does not appear to maintain a separate human-readable "memory file" for compacted conversation state.

Instead, it:

1. Detects that the conversation should be compacted.
2. Builds a dedicated summarization prompt.
3. Sends that prompt to a model with tool use disabled.
4. Wraps the model output into a synthetic continuation message.
5. Replaces older transcript context with:
   - a `compact_boundary` system marker
   - zero or more kept recent messages
   - one or more compact summary messages
   - attachments and hook results when applicable

The compacted memory is therefore best understood as model-generated transcript replacement, not as a separate local database artifact.

## On-Disk Representation

The strongest local evidence is in real Claude transcript JSONL files.

Example transcript:

- `~/.claude/projects/-Users-nigelleong-Desktop-WORK-antalpha-ai-skills-library/4369b070-222a-4bda-bbc9-e418248b4155.jsonl`

The compaction boundary is stored as a system message:

```json
{
  "type": "system",
  "subtype": "compact_boundary",
  "content": "Conversation compacted",
  "compactMetadata": {
    "trigger": "auto",
    "preTokens": 167255
  }
}
```

Immediately after that, Claude Code writes a synthetic compact summary message. Its content begins with:

```text
This session is being continued from a previous conversation that ran out of context.
The summary below covers the earlier portion of the conversation.
```

Observed summaries then continue with structured sections such as:

- `Analysis:`
- `Summary:`
- `Primary Request and Intent`
- `Key Technical Concepts`
- `Files and Code Sections`
- `Pending Tasks`
- `Current Work`

This is the core evidence that compacted memory is stored back into the transcript as a continuation summary message.

## Triggering Compaction

Runtime logs show both automatic and manual compaction paths.

Observed debug messages include:

```text
Conversation compacted (ctrl+o for history)
autocompact: tokens=37800 threshold=167000 effectiveWindow=180000
```

This indicates:

- automatic compaction occurs near a token threshold
- the UI exposes compact history to the user
- compaction is treated as a runtime transcript rewrite rather than a background hidden cache

## Microcompact

In addition to full conversation compaction, Claude Code also has a lighter-weight `microcompact` path.

Recovered boundary construction shows a distinct transcript marker with metadata:

```text
type: "system"
subtype: "microcompact_boundary"
content: "Context microcompacted"
microcompactMetadata: {
  trigger,
  preTokens,
  tokensSaved,
  compactedToolIds,
  clearedAttachmentUUIDs
}
```

This is different from full `compact_boundary` because it does not create a continuation summary message for the whole conversation.

### What Microcompact Appears To Remove

Recovered logic from `Av(...)` suggests that `microcompact` primarily targets bulky tool and attachment context, not the full visible conversation:

- it scans message content for `tool_use` entries whose tool names are in an internal allowlist
- it tracks matching `tool_result` payloads and estimates their token cost
- it ignores the most recent few tool calls
- it can replace large `tool_result` content with a saved-file placeholder
- it can replace user-supplied images and documents with `[image]` or `[document]`
- it keeps track of compacted tool IDs and cleared attachment UUIDs so the runtime knows those payloads were already trimmed

Recovered microcompact tool allowlist includes internal names corresponding to file read, search, edit, shell, web fetch, and other high-volume tools.

The strongest binary clue for the replacement format is a separate internal message type:

```text
tool_use_summary
```

Recovered helper `AbB(...)` builds a very short model-generated summary from completed tools only, using the prompt:

```text
You summarize what was accomplished by a coding assistant.
Given the tools executed and their results, provide a brief summary.
```

Rules recovered from the binary include:

- use past tense
- be specific
- keep under 8 words
- focus on user-visible outcome

This strongly suggests that Claude Code can collapse some tool-heavy spans into short tool summaries rather than full conversation summaries. That said, the local transcripts examined for this pass did not expose persisted `tool_use_summary` records directly, so the exact storage shape remains a moderate-confidence reconstruction.

### Why Microcompact Looks Like Hidden-Context Trimming

Observed local transcript metadata shows cases where `preTokens` is low but `tokensSaved` is very high.

For example, some sessions record `tokensSaved` values in the tens of thousands while the visible pre-compact transcript token count is much smaller. That pattern is hard to explain with plain visible message text alone and fits much better with:

- large tool results
- attachment payloads
- hidden or transcript-suppressed tool context

The best current interpretation is that `microcompact` is a context-budget protection layer for bulky tool and attachment state, while full compaction is the conversation-level summarization layer.

## Token Estimation And Thresholds

Claude Code appears to use two token mechanisms at runtime:

1. API-reported usage from the last real assistant response
2. local heuristic estimation for any newer transcript items not yet covered by API usage

The automatic compaction check is not a pure server-side number and not a pure local tokenizer either. It is a hybrid.

### API Usage Path

Recovered helpers:

- `Dm(T)` extracts `message.usage` from an assistant response
- `WjT(usage)` sums:
  - `input_tokens`
  - `cache_creation_input_tokens`
  - `cache_read_input_tokens`
  - `output_tokens`

Recovered helper:

```text
pL(T)
```

walks backward through the transcript and returns the latest available assistant usage total.

This matches what is visible in real transcript JSONL files, where assistant messages store usage fields such as:

- `input_tokens`
- `output_tokens`
- `cache_creation_input_tokens`
- `cache_read_input_tokens`

### Local Incremental Estimate

Recovered helper:

```text
df(T)
```

computes the value logged by:

```text
autocompact: tokens=${_} threshold=${B} effectiveWindow=${D}
```

Its logic is:

1. find the latest assistant message that has real API usage
2. sum that usage via `WjT(...)`
3. add a local estimate for transcript items after that point

That local estimate is built from:

- `G2A(T)` for a list of transcript items
- `C2A(T)` for a single transcript item
- `q2A(content)` for message content
- `P$7(block)` for individual content blocks

The recovered heuristics are simple:

- text: approximately `Math.round(length / 4)`
- image: fixed `2000`
- `tool_result`: recurse into its content
- attachments: expand and recurse into attachment-derived content

So `df(T)` is best understood as:

```text
latest real assistant usage total
+ heuristic estimate for newer local transcript items
```

This is the strongest evidence that autocompact decisions are made locally by Claude Code rather than waiting for the next model response to report updated usage.

### Context Window And Threshold Math

Recovered threshold helpers:

- `F$T(model)` computes an effective context window
- `GcT(model)` computes the auto-compact trigger threshold
- `Ep(tokens, model)` evaluates warning, error, auto-compact, and blocking thresholds

Recovered current constants in this build indicate:

- effective window derived from model context minus reserved buffer
- auto-compact threshold further reduced below that effective window
- separate warning, error, and blocking limits

The observed debug output:

```text
autocompact: tokens=151683 threshold=167000 effectiveWindow=180000
```

fits that model exactly:

- `effectiveWindow=180000` is the budget Claude Code treats as usable prompt space
- `threshold=167000` is the earlier line where auto-compaction should start
- `tokens=...` is the hybrid local estimate from `df(T)`

### Where Count-Tokens API Still Appears

Claude Code also includes a real count-tokens API path:

- `JjT(...)`
- `wmT(...)`
- `countTokensWithFallback`

This path calls model-side token counting and falls back when needed. It appears to be used for:

- system prompt token analysis
- tool definition token analysis
- memory and skills token accounting
- diagnostics and status views

It does not appear to be the hot path for the `autocompact: tokens=...` runtime check, which is handled by `df(T)` instead.

## Compaction Pipeline

Recovered bundled symbol names strongly suggest two main entry paths:

- `dET(...)`
  - normal full-conversation compaction used by automatic or manual summarize flows
- `CyB(...)`
  - partial or recent-only compaction used by message selector summarize flows

Both routes converge on the same pattern:

1. Build compaction instructions.
2. Package a summary request.
3. Call the model through a compaction-specific request path.
4. Extract text from the assistant reply.
5. Wrap that text as a continuation message.
6. Replace prior history with compacted state.

### Full Compaction Path

Recovered flow from `dET(...)`:

```text
pre-compact hooks
-> WZ_(customInstructions)
-> summaryRequest
-> WyB(...)
-> nLT(responseText)
-> QjT(summaryText, ...)
-> compact_boundary + summaryMessages + attachments + hookResults
```

Important behaviors visible in the binary:

- pre-compact hooks are passed trigger metadata such as `auto` or `manual`
- custom compact instructions can be injected into the summary prompt
- the response is marked as `isCompactSummary: true`
- the compact summary is transcript-visible only in a specialized way

### Partial / Recent-Only Compaction Path

Recovered flow from `CyB(...)`:

```text
split kept messages from summarized messages
-> JZ_(customInstructions)
-> summaryRequest
-> WyB(...)
-> nLT(responseText)
-> QjT(summaryText, ...)
-> compact_boundary + messagesToKeep + summaryMessages + attachments + hookResults
```

This path explains why some recent messages can remain verbatim while earlier history is collapsed into a single continuation summary.

## The Model Call

The recovered compaction request helper is `WyB(...)`.

This is the clearest evidence that compaction itself is delegated to a model instead of a local deterministic summarizer.

Relevant recovered behavior:

- it tries a cache-sharing path first
- if that is not used, it falls back to a normal assistant request
- the compaction system prompt is:

```text
You are a helpful AI assistant tasked with summarizing conversations.
```

- thinking is explicitly disabled:

```text
thinkingConfig: { type: "disabled" }
```

- tool use is explicitly denied during compaction

Recovered restriction text:

```text
Tool use is not allowed during compaction
```

This means the summary that becomes compacted memory is not produced by local heuristics. It is generated by a model call on top of the conversation state selected for compaction.

## Recovered Compaction Prompt Templates

### Full-Conversation Prompt Builder

The full compaction prompt builder appears as `WZ_(T)`.

Recovered semantics:

- asks for a detailed summary of the conversation so far
- requires preserving actionable technical state, not just a short recap
- allows caller-supplied custom compact instructions
- requires output to be only a tagged summary block

Recovered required sections:

1. `Primary Request and Intent`
2. `Key Technical Concepts`
3. `Files and Code Sections`
4. `Errors and fixes`
5. `Problem Solving`
6. `All user messages`
7. `Pending Tasks`
8. `Current Work`
9. `Optional Next Step`

Recovered hard constraint:

```text
IMPORTANT: Do NOT use any tools. You MUST respond with ONLY the <summary>...</summary> block as your text output.
```

### Recent-Only Prompt Builder

The recent-only prompt builder appears as `JZ_(O)`.

Recovered semantics:

- summarize only the recent portion selected for compaction
- avoid re-summarizing earlier context that is still being kept
- produce the same structured output format expected by downstream formatting

This is consistent with the partial compaction path returning both `messagesToKeep` and `summaryMessages`.

## Summary Post-Processing

The recovered formatter `QjT(...)` wraps the raw summary into the continuation text that shows up in the transcript.

Recovered leading text:

```text
This session is being continued from a previous conversation that ran out of context.
The summary below covers the earlier portion of the conversation.
```

Recovered optional additions include text equivalent to:

- recent messages are preserved verbatim
- the assistant should continue from where the conversation left off
- the full transcript can be consulted if specific pre-compaction details are needed

Another recovered helper, `p$7(...)`, appears to translate tagged blocks like `<analysis>` and `<summary>` into the plain-text sections visible in the stored continuation message:

- `Analysis:`
- `Summary:`

## Why This Counts As "Compacted Memory"

Claude Code's compacted memory is not a separate subsystem with its own file format.

It is the combination of:

- a `compact_boundary` marker
- a model-generated continuation summary
- any verbatim recent messages intentionally preserved
- attachments and hook outputs that still need to survive compaction

That compacted transcript state becomes the new context base for future turns.

## Confidence Notes

High confidence:

- compaction is represented in transcript JSONL with `compact_boundary`
- the continuation summary message is model-generated and stored back into the transcript
- `WyB(...)` performs a model request with a compaction-specific system prompt
- tool use is disabled during compaction
- `WZ_(...)` and `JZ_(...)` are prompt builders for full and partial compaction flows

Moderate confidence:

- exact internal responsibilities of some helper symbols beyond the recovered text and call graph
- whether all compaction variants in other Claude Code versions use the same symbol names or only the same logic
- the exact persisted representation of `tool_use_summary` in all runtime modes, because it did not appear directly in the local transcript samples examined here

## Related Reference

For the broader reconstructed Claude Code prompt assembly outside compaction, see:

- `docs/references/claude-code-prompts-v2.1.47.md`
