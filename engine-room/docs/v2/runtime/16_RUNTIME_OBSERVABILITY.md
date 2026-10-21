# 16 — Runtime Observability

**Status:** design only. Defines how the Runtime Manager (RM) exposes telemetry,
tracing, metrics, runtime health, and session metrics — **by reusing the existing
Phase 2 Observability substrate** (`nexus_infra/observability.py`). RM invents no new
telemetry mechanism. Everything here is **derived** and **read-only**: it is computed
*from* facts, it is never itself a fact. The authoritative facts are the `runtime.*`
event log (`15_RUNTIME_EVENTS.md`, ADR-001) and the Registry's health/availability
(`04_RUNTIME_REGISTRY.md`, INV-36).

---

## 1. The one rule: telemetry is never the truth

There are two distinct planes, and they must never be confused:

```
   AUTHORITATIVE PLANE                         DERIVED PLANE
   (state / audit — source of truth)           (observability — never the truth)
   ┌──────────────────────────────┐            ┌──────────────────────────────────┐
   │  runtime.* EVENT LOG  (15)    │  fold ───▶ │  counters / gauges / timings /    │
   │  → Session state projection   │            │  traces / health snapshots        │
   │  (ADR-001, INV-16)            │            │  (Observability substrate)        │
   ├──────────────────────────────┤            └──────────────────────────────────┘
   │  Registry health/avail (INV-36)│                       │
   └──────────────────────────────┘                        ▼
                                                consumed by Supervision / ops / Recovery
```

- **State and audit** come *only* from the `runtime.*` event log (and from the
  Registry for health/availability). The Runtime Session's lifecycle state, allocation
  state, progress, artifact set, and error are projections of that log (`02` §5,
  `07` §5).
- **Observability** — counters, gauges, traces, timings — is **folded out of the same
  facts** for humans and tooling. It is a convenience view, not a control input. RM
  takes no decision (selection, allocation, lifecycle transition, teardown) on the
  basis of a metric or trace.
- **Losing observability never corrupts state.** If the Observability sink is the
  default `NullObservability` (records nothing) or drops every sample, the session
  still progresses identically, because state replays from the log alone. Telemetry is
  lossy by design; the event log is not. This is the inverse guarantee of the substrate
  itself, which "stores nothing durably, and never influences projected state."

> If a number disagrees with the event log, the event log wins, always. A metric is a
> hint; the log is the record.

## 2. The substrate RM reuses (no new mechanism)

RM emits through the **existing** Phase 2 `Observability` sink — the same three
primitives every prior layer uses, plus structured instrumentation records:

| Substrate primitive | RM's use |
|---|---|
| `record(InfraEvent)` | structured instrumentation record about an internal step (e.g. an intake validation, an allocation reservation, a stream-buffer event) — *not* a domain `runtime.*` event |
| `increment(name)` | monotonic counters (terminal outcomes, artifacts emitted, candidates dropped, timeouts fired) |
| `observe(name, value)` | distribution samples (allocation latency, time-to-ready, execution duration, stream throughput) |
| `timed(clock, sink, metric)` | the standard span-timer wrapper for measuring a bounded preparation step |

Two record kinds must not be confused:

- A **domain event** is a `runtime.*` `Event` on the canonical envelope (`15`) — it is
  state-bearing and authoritative.
- An **`InfraEvent`** (`InfraEventType`, from the substrate) is an *instrumentation*
  record — "not a domain Event," by the substrate's own definition. RM uses the
  substrate's existing `InfraEventType` members for infra-level concerns (append,
  publish, projection, snapshot, concurrency conflict) and never coins a `runtime.*`
  name inside `InfraEvent`. Observability **reads** `runtime.*`; it does not re-author
  it.

## 3. Metric & trace categories

All categories below are derived; each names its authoritative source event(s) from
`15`. Names are illustrative groupings, not a schema.

### 3.1 Preparation timings (the deterministic core)

| Category | What it measures | Folded from (15) |
|---|---|---|
| allocation latency | reserve→allocate wall time for one runtime | `runtime.allocated` (vs `candidates_resolved`) |
| queue / wait time | time a package waited before allocation began | `runtime.session_created` → `runtime.allocated` |
| time-to-ready | session_created → ready (full preparation cost) | `runtime.session_created` → `runtime.ready` |
| candidate attrition | candidates dropped at match/health/policy | `runtime.candidates_resolved`, `runtime.capabilities_matched` |

### 3.2 Execution timings & throughput (observed, not performed)

| Category | What it measures | Folded from (15) |
|---|---|---|
| execution duration | started → terminal (process runtime, not validation) | `runtime.started` → `runtime.completed` / `cancelled` / `failed` |
| stream throughput | output volume/rate over the stream (`08`) | `runtime.output` chunk sequence |
| progress velocity | rate of progress advance, where progress is known (`12`) | `runtime.progress` |
| pause / wait dwell | time spent in `Paused` / `Waiting` | `runtime.paused`/`waiting_approval` → `runtime.resumed` |

### 3.3 Liveness gauges

| Category | What it measures | Folded from (15) |
|---|---|---|
| heartbeat gauge | most recent liveness ping per live session (`10`) | `runtime.heartbeat` |
| inactivity gauge | now − last_activity, for inactivity-timeout reasoning | last `runtime.output`/`heartbeat` (`02` §5) |

These gauges *inform* the timeout model (`10`) as derived hints; the timeout itself
fires as a `runtime.timed_out` **event** (the authoritative fact), never as a metric
threshold. The gauge is the dashboard; the event is the decision.

### 3.4 Outcome & artifact counters

| Category | What it measures | Folded from (15) |
|---|---|---|
| terminal-outcome counters | per-outcome tally (`completed` / `cancelled` / `failed`) | `runtime.completed`/`cancelled`/`failed` |
| timeout counters | timeouts by kind (`10`) | `runtime.timed_out` |
| artifact counts | Evidence Candidates / outputs emitted per session (`13`) | `runtime.artifact_emitted` |
| checkpoint counts | checkpoints associated per session (`02`) | `runtime.checkpoint_captured` |

### 3.5 Per-runtime health & availability (read, not owned)

| Category | What it measures | Source |
|---|---|---|
| availability snapshot | per-runtime `ResourceAvailability` (`available/busy/reserved/offline/maintenance/failed/unknown`) | **Registry**, INV-36 (read) |
| health probe result | optional adapter-exposed liveness signal | adapter probe (`03`), surfaced — not owned |

## 4. Session metrics vs aggregate runtime metrics

Two scopes, never merged:

| Scope | Keyed by | Examples | Primary consumer |
|---|---|---|---|
| **Session metrics** | session id (one attempt, `02`) | this session's time-to-ready, execution duration, artifact count, inactivity gauge, terminal outcome | Supervision (per-execution), audit (`18`) |
| **Aggregate runtime metrics** | runtime identity (over many sessions) | this runtime's allocation-latency distribution, success/failure ratio, mean throughput, current availability | ops / capacity planning, Selection inputs (`06`) |

- A **session metric** is a single execution attempt's derived figures, correlated to
  its `correlation_identifier` so it nests in the Goal's lineage (§5).
- An **aggregate runtime metric** rolls session metrics up by runtime to characterize a
  runtime's behavior over time. A retry that lands on a *different* runtime (`02` §6)
  contributes one session metric to each runtime's aggregate, but remains one causal
  attempt history under the shared correlation.
- Aggregates are **derived from** session-scoped facts; they never become authoritative
  capacity state. Capacity/quotas are deferred (`20_RUNTIME_GAPS.md`).

## 5. Tracing via the shared correlation/causation lineage (INV-39)

RM does not open a private tracing system. It rides the **operation-wide
correlation/causation lineage** every event already carries (`15` §3, INV-39):

- Every `runtime.*` event shares the Goal's `correlation_identifier`, so a runtime
  **span** nests inside the end-to-end trace:
  `Goal → Context → Plan → Orchestration → Harness → Runtime`. The runtime span is the
  innermost segment of that single causal stream — not a sibling tree.
- `causation_identifier` links cause→effect across subsystems (e.g. a
  `runtime.resumed` caused by an approval-grant from `14`), so a trace viewer can show
  *why* a transition happened, not just *that* it did.
- Within a session, the **monotonic sequence** on each event gives a total order, so a
  session timeline reconstructs exactly from the log (`02` §5, `15` §3).

```
   Goal trace (one correlation_identifier)
   └─ context span
      └─ plan span
         └─ orchestration span
            └─ harness span
               └─ RUNTIME SESSION span  ← RM's contribution
                  ├─ prepare (session_created → ready)   [time-to-ready]
                  ├─ run     (started → completed)        [execution duration]
                  └─ teardown(released → destroyed)
```

A runtime trace therefore needs no new id space: it is a *view* over the existing
lineage. Lose the trace and the lineage is still fully reconstructable from the log.

## 6. Runtime health — read from the Registry, never owned

Health is **owned by the Harness Registry** (INV-36); RM is a reader.

- RM **reads** each runtime's `ResourceAvailability` and health from the Registry view
  (`04`) when filtering candidates (pipeline step 4, `01` §4) and when reporting a
  runtime's current state.
- RM **may probe** a runtime through its adapter where the runtime exposes a health
  signal (`01` §2.4, `03`) and surface the probe result as a derived observation — but
  the probe result is a *reading*, not a new owned state. RM never writes a competing
  health record, never overrides the Registry, and never lets a stale metric stand in
  for current availability.
- `OperationalHealth` classification (`healthy/degraded/stalled/…`) and intervention
  recommendations are **Supervision's** to compute (future); RM supplies the derived
  inputs (heartbeat/inactivity gauges, outcome counters) but issues no classification
  itself (`20_RUNTIME_GAPS.md`).

## 7. Observability category → source event → consumer (the map)

| Observability category | Source event(s) (15) | Primary consumer |
|---|---|---|
| time-to-ready / queue / allocation latency | `session_created`, `candidates_resolved`, `allocated`, `ready` | ops / capacity, Selection inputs (`06`) |
| execution duration | `started` → `completed`/`cancelled`/`failed` | Supervision, ops |
| stream throughput | `output` | Supervision, ops |
| progress velocity | `progress` | Supervision |
| heartbeat / inactivity gauges | `heartbeat`, `output` | Supervision, timeout reasoning (`10`) |
| pause / wait dwell | `paused`, `waiting_approval`, `resumed` | Supervision, governance/audit (`18`) |
| artifact / checkpoint counts | `artifact_emitted`, `checkpoint_captured` | Validation discovery (`13`), Recovery (`02`) |
| timeout counters | `timed_out` | Recovery, ops |
| terminal-outcome counters | `completed`, `cancelled`, `failed` | Recovery, ops, Supervision |
| availability / health snapshot | Registry (INV-36) + adapter probe | RM filtering (`06`), ops |
| correlation/causation trace | every `runtime.*` (shared lineage) | end-to-end tracing, audit (`18`) |

Consumers **react to** these derived views; none of them write back into RM's session
state. The log is one-way truth (`15` §5).

## 8. Invariants this document honors

| Invariant / ADR | How honored |
|---|---|
| **ADR-001** event-sourced state | observability is folded *from* the `runtime.*` log; state is never read from metrics |
| **INV-16** idempotent consumption | folding a metric from a deduped log is itself idempotent; replay yields identical derived figures |
| **INV-17** timestamps are recorded data | timings derive from event-payload timestamps; the substrate's clock is injected, recorded only as samples |
| **INV-36** Registry owns health/availability | RM **reads** availability/health; probes surface readings, never owned state |
| **INV-39** one correlation lineage | runtime spans nest in the Goal's end-to-end trace; no private trace id space |

## 9. One-paragraph mental model

The Runtime Manager already emits everything that matters as `runtime.*` events; the
event log is the truth, and the session state is its projection. Observability is the
*second*, throwaway reading of those same facts: counters for how often things happen,
gauges for what's live right now, timings for how long steps took, and traces that
nest the runtime span inside the Goal's one correlation lineage — all flowing through
the existing Phase 2 Observability sink, owning nothing, deciding nothing, and read
for health by Supervision/ops/Recovery. Pull the sink and the system runs identically.
Observability is how Nexus *watches* the runtime; it is never how Nexus *knows* the
runtime.
