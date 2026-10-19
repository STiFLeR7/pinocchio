# 08 — Streaming Model

**Status:** design only. Defines how the Runtime Manager streams a runtime's output —
stdout, stderr, structured events, progress updates, logs, and intermediate artifacts —
**runtime-independently**, so the same model serves Claude Code, Gemini CLI, Shell,
Docker, Browser, Python, MCP, remote workers, and runtimes not yet imagined. Streaming
is a supervision concern (`01` step 13): it occurs while the Execution Engine performs
the work; RM only **observes and records**.

---

## 1. Principles

- **Runtime-independent.** RM core never sees a provider's raw byte format. Each
  runtime's output funnels into one normalized shape through its **Runtime Adapter**
  (`03`); the adapter is the only place that knows how a given runtime emits.
- **Event-sourced (ADR-001).** Every streamed unit becomes a canonical `runtime.output`
  event (`15`) on the session's `runtime.*` log. The session's reconstructable output is
  a **projection** of that log — RM keeps no separate, authoritative stream buffer.
- **Recorded, not decided.** A stream carries an external fact about what the runtime
  emitted. **Streaming carries no decisions.** It never declares success, never grades,
  never validates, never triggers retry. Completion is the lifecycle's (`07`) and
  Validation's concern (INV-20), not the stream's.
- **Observed during Running.** Streaming happens in lifecycle state `Running` (`07`) and
  may continue to be projected while `Paused`/`Waiting`; a paused session simply stops
  producing new output until it resumes.
- **Deterministic identity, recorded timestamps.** Each output event id is
  `f(session id, kind, sequence)` (`15`); wall-clock lives only in the payload (INV-17).
  Replay reproduces the identical ordered stream (INV-16).

## 2. The normalized stream channel

Every byte or structured unit a runtime emits is normalized by the adapter into a
**stream channel** — a small, closed classification that RM core understands without
knowing the runtime. Four channels are defined; they are the *only* shapes RM core sees:

| Channel | Carries | Examples across runtimes |
|---|---|---|
| **stdout** | the runtime's primary output stream | shell command output, Python `print`, container stdout |
| **stderr** | the runtime's diagnostic/error stream | shell errors, stack traces, container stderr |
| **structured** | machine-readable, typed units the runtime emits natively | Claude Code tool-call/turn events, MCP JSON-RPC notifications, browser DOM/console events |
| **log** | runtime/adapter operational logging about the run itself | adapter lifecycle notes, retry/setup logging, environment notes |

> The channel is a **transport classification**, not a meaning. `stderr` does not imply
> failure; `structured` does not imply a decision. Interpretation (if any) is a later
> phase's job. RM only records *which channel* a unit arrived on.

### 2.1 Why funnel everything into one shape

Because every runtime's emission is reduced to `{channel, sequence, payload-or-ref}`,
RM core's supervision logic — ordering, inactivity reasoning (`10`), artifact promotion
(§5), telemetry (`16`) — is written **once** and works for all runtimes. Adding a new
runtime (`19`) means writing an adapter that maps its native output onto these four
channels; RM core is untouched.

## 3. Ordering & sequencing

- **Monotonic per-session sequence.** Each streamed unit is assigned the next sequence
  number within its session, giving a **total order** for replay and a **dedupe key**
  (INV-16). The sequence is the same monotonic counter that orders all `runtime.*`
  events (`02` §3, `15` §3), so output, progress (`12`), heartbeats (`10`), and artifact
  emissions (`13`) interleave on **one ordered timeline**.
- **Channels share one timeline.** stdout and stderr are not separately ordered streams;
  they are ordered by their shared session sequence, so the causal relationship between,
  say, a structured tool-call and the stderr it produced is preserved.
- **Replayable.** Folding the `runtime.output` events in sequence order reconstructs the
  exact session output (ADR-001). RM may take a snapshot plus tail replay (`02` §5) but
  the log remains authoritative.
- **Adapter responsibility.** Where a runtime emits genuinely concurrent streams (e.g. a
  container's stdout and stderr arriving in parallel), the adapter assigns sequence at
  the normalization boundary; RM core receives an already-ordered stream.

```
runtime (provider-specific)        adapter (03)              RM core (generic)
─────────────────────────          ───────────              ─────────────────
raw stdout bytes        ┐
raw stderr bytes        ├─ normalize ─▶ {channel, seq, payload|ref} ─▶ runtime.output event
native structured event ┘                                              (sequence-ordered,
                                                                        replayable log)
```

## 4. Backpressure, volume & truncation (design responsibility)

These are **design responsibilities recorded here**, not implementation; the future
implementation must honor them but is free to choose mechanisms.

- **Backpressure.** A runtime may emit faster than RM can persist. The design REQUIRES a
  bounded path: the adapter/RM must apply backpressure or buffering with a defined bound,
  never unbounded memory growth, and never silently drop in a way that breaks replay.
- **Volume / large units.** A single output unit may be large (a multi-megabyte log dump,
  a big structured payload). Large units MUST NOT be embedded inline in a
  `runtime.output` event payload; they cross over into the **artifact path** (§5) and are
  referenced by id, keeping the event log small and the artifact immutable (`13`).
- **Truncation.** Where a stream must be truncated for an inline event (e.g. a preview
  line), truncation MUST be **explicit and recorded** — the event notes that it is a
  truncated view and references the full content as an artifact (`13`). The
  no-silent-correction rule applies: a truncated stream is never presented as complete.
- **Loss visibility.** If output is lost (buffer overrun, adapter crash), that gap is
  surfaced as a recorded fact (an error in `11` and/or an explicit gap marker), never
  hidden. Replay must reveal the gap, not paper over it.

> RM never *edits* stream content to make it smaller or cleaner — it either records it,
> references it as an artifact, or records an explicit truncation/gap. Mutating a
> runtime's output would be deciding something; streaming decides nothing.

## 5. From stream to event vs. stream to artifact

Two destinations exist for streamed output; the **size/role** of the unit decides which,
not the runtime identity:

| Condition | Destination | Carrier |
|---|---|---|
| Small, line/chunk-level output | inline on the log | `runtime.output` event (`15`), channel + sequence + payload |
| Large, durable, or completion-relevant output (full log, file, structured result) | referenced, not embedded | a `runtime.artifact_emitted` event (`13`) pointing to an **Evidence Candidate** by id |

- A continuous **log stream** is projected live as `runtime.output` units **and** may be
  finalized as a **log artifact** (`13`) when the run ends, so consumers get both the
  live tail and an immutable whole. The artifact is referenced by id (INV-12); RM holds
  the reference, not the bytes.
- The boundary between "stream it" and "reference it as an artifact" is the same
  boundary §4 draws for volume/truncation — they are one design rule viewed twice.
- RM **collects and associates** the resulting artifact references on the session (`02`
  §8); it never grades them. Validation later promotes Candidates to Evidence (INV-20).

## 6. Relationship to heartbeats, inactivity & progress

- **Heartbeats / inactivity (`10`).** Any `runtime.output` advances the session's
  **last-activity** marker (`02` §5), which inactivity-timeout reasoning consumes (`10`).
  A runtime that streams is, by definition, live. When a runtime is working but silent,
  liveness is asserted by `runtime.heartbeat` (`10`) rather than output — streaming and
  heartbeats are complementary liveness signals on the same timeline.
- **Progress (`12`).** Progress updates are a **distinct** signal, carried by
  `runtime.progress`, not derived by RM from scraping stdout. Where a runtime expresses
  progress only inside its log/structured output, the **adapter** extracts it and emits a
  normalized `runtime.progress` (`12`); RM core does not parse provider text. Streaming
  carries the raw output; progress carries the interpreted advisory snapshot — kept
  separate so neither contaminates the other.

## 7. Per-runtime channel mapping (comparison)

How each runtime's native emission maps onto the four normalized channels. The mapping
lives entirely in that runtime's adapter (`03`); RM core sees only the right-hand shape.

| Runtime | stdout | stderr | structured | log |
|---|---|---|---|---|
| **Shell** | command stdout | command stderr | (none; adapter may synthesize from exit/markers) | adapter run notes |
| **Docker** | container stdout stream | container stderr stream | container events (start/oom/exit) as structured | engine/adapter operational log |
| **Claude Code** | assistant text output | tool/runtime errors | turn / tool-call / tool-result events as structured | adapter session log |
| **Browser** | page console.log | page console.error / page errors | DOM/network/navigation events as structured | driver/adapter log |
| **Python** | process stdout | process stderr / tracebacks | structured results the script emits (e.g. typed records) | interpreter/adapter log |
| **MCP** | textual tool output | tool/protocol errors | JSON-RPC results & notifications as structured | transport/adapter log |
| **Remote worker** | worker stdout (relayed) | worker stderr (relayed) | worker structured events (relayed) | transport/adapter log |

Reading the table: a runtime with no native structured channel (e.g. plain Shell) simply
has an empty `structured` column — that is **normal**, not an error. RM core's logic does
not require any particular channel to be populated; it records whatever the adapter
normalizes.

## 8. What the streaming model is *not*

- Not a completion signal — process end is `runtime.completed` (`07`/`15`); success is
  Validation's (INV-20).
- Not progress — progress is `runtime.progress` (`12`), produced deliberately, not
  scraped by RM core.
- Not a place for decisions — streaming records facts; it never validates, grades,
  retries, or recovers.
- Not a byte store for large output — large/durable output is referenced as an immutable
  artifact (`13`), never embedded in the event log.

## 9. Cross-references

`00` (overview, inputs/outputs) · `01` (supervision step 13) · `02` (session state,
last-activity, artifact association) · `03` (adapter normalization boundary) ·
`07` (Running/Paused/Waiting states) · `10` (heartbeats, inactivity timeouts) ·
`11` (typed errors, gap/loss surfacing) · `12` (progress model) · `13` (artifact model) ·
`15` (`runtime.output` and sibling events) · `16` (telemetry from the stream) ·
`19` (adding a runtime adapter without touching RM core).
