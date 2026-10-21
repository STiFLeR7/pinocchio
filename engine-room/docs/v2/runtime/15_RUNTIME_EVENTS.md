# 15 — Runtime Events

**Status:** design only. Defines the canonical `runtime.*` event taxonomy — the
authoritative facts the Runtime Manager emits. Session state is a *projection* of this
stream (ADR-001). Every other document references these names; none may coin a
competing event.

---

## 1. Principles

- **Event-sourced (ADR-001).** The `runtime.*` log is authoritative; the Runtime
  Session's state (`07`), progress (`12`), allocation (`06`), and artifact set (`13`)
  are all projections folded from it.
- **One envelope.** Every runtime event is the platform's canonical `Event` (Phase 1):
  `producer = "runtime"`, `source = "nexus_runtime"`, a deterministic `identifier`, the
  shared `correlation_identifier` (INV-39), and a `timestamp` recorded as data
  (INV-17). RM invents no new event shape.
- **Idempotent (INV-16).** Event identifiers are deterministic and dedup-keyed; a
  duplicate or out-of-order delivery causes no duplicate effect on the projection.
- **Deterministic ids.** `event id = f(session id, kind, sequence)` — pure function, no
  clock/counter/randomness in the *id* (the wall-clock lives only in the payload).
- **Recorded, not decided.** Events that report runtime behavior (output, progress,
  completion) capture an external fact; they encode no decision RM is forbidden to make
  (it does not validate, recover, or reason).

## 2. Canonical event taxonomy

Grouped by lifecycle phase. (Names are canonical; payload sketches are illustrative,
not a schema — no implementation here.)

### Preparation
| Event | Emitted when | Key payload (illustrative) |
|---|---|---|
| `runtime.session_created` | session bound (package ⇄ runtime), state `Created` | session, package, node, correlation, attempt |
| `runtime.candidates_resolved` | candidate descriptors read from the Registry | session, candidate count |
| `runtime.capabilities_matched` | capability match completed (`05`) | session, required, satisfied, unsupported |
| `runtime.allocated` | a runtime reserved+allocated (`06`) | session, runtime, allocation, allocation_state |
| `runtime.prepared` | configuration rendered, state `Prepared` | session, isolation_profile (no secrets) |
| `runtime.ready` | readiness checks pass, state `Ready` | session |

### Execution (observed/supervised)
| Event | Emitted when | Key payload |
|---|---|---|
| `runtime.started` | engine begins; state `Running` | session, runtime |
| `runtime.output` | a stream chunk (stdout/stderr/structured) (`08`) | session, channel, sequence, bytes/line ref |
| `runtime.progress` | a progress update (`12`) | session, phase, fraction-or-unknown, milestone |
| `runtime.heartbeat` | liveness ping (`10`) | session, last_activity |
| `runtime.artifact_emitted` | an Evidence Candidate / output referenced (`13`) | session, artifact_ref, kind |
| `runtime.checkpoint_captured` | a checkpoint associated (`02`/recovery) | session, checkpoint_ref |
| `runtime.paused` | suspended; state `Paused` (`09`) | session, reason |
| `runtime.waiting_approval` | blocked on approval; state `Waiting` (`14`) | session, approval_ref, taxonomy |
| `runtime.resumed` | returned to `Running` from Paused/Waiting | session, from_state |

### Terminal & teardown
| Event | Emitted when | Key payload |
|---|---|---|
| `runtime.completed` | process ended normally; state `Completed` | session, artifact_refs, exit_status |
| `runtime.cancelled` | cancellation took effect; state `Cancelled` (`09`) | session, mode (graceful/forced), reason |
| `runtime.timed_out` | a timeout fired (`10`) — precedes cancel/fail | session, timeout_kind |
| `runtime.failed` | typed error ended the session; state `Failed` (`11`) | session, error_class, owner, detail |
| `runtime.released` | allocation returned to `RELEASED` (`06`) | session, runtime, allocation |
| `runtime.destroyed` | cleanup done; state `Destroyed` (`07`) | session, outcome |

## 3. Ordering & correlation

- Within a session, events carry a **monotonic sequence**, giving a total order for
  replay and a dedupe key (INV-16).
- Across the platform, every runtime event shares the operation's
  **`correlation_identifier`** (INV-39), so a single Goal's lineage —
  Goal → Context → Plan → Orchestration → Harness → **Runtime** — is one queryable
  causal stream.
- `causation_identifier` links an event to the event that directly caused it (e.g. a
  `runtime.resumed` caused by an approval-grant event from `14`), preserving cause→effect
  chains across subsystems.

## 4. What is *not* a runtime event

- **Validation verdicts** (`evidence.*`, `validation.*`) — Validation emits those from
  Evidence; RM emits `runtime.completed` (process ended), never "validated."
- **Recovery decisions** (`recovery.*`) — Recovery owns retry/rollback/abort; RM emits
  `runtime.failed` and stops.
- **Orchestration/Harness facts** — RM does not re-emit upstream events; it references
  them by id/correlation.

## 5. Consumers

| Consumer | Uses the stream for |
|---|---|
| Runtime Session projection (`02`/`07`) | authoritative current state |
| Observability (`16`) | metrics, traces, health, session timelines |
| Supervision (future) | health classification, intervention recommendations |
| Validation (future) | discovering emitted Evidence Candidates (`runtime.artifact_emitted`) |
| Recovery (future) | reacting to `runtime.failed` / `runtime.timed_out` |
| Governance/audit (`18`) | the immutable record of allocation, approval, and outcome |

Consumers **react to** the log; none of them write back into RM's session state — the
log is the one-way source of truth.
