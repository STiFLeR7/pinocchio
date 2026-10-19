# 09 — Cancellation Model

**Status:** design only. Defines how the Runtime Manager (RM) stops a running session
on demand: **graceful** cancellation (ask the runtime to stop and let it clean up),
**forced** cancellation (hard kill when graceful fails or is impossible), **timeout
escalation** (how a timeout from `10_TIMEOUT_MODEL.md` becomes a cancellation), and the
**cleanup responsibilities** the adapter owns on every terminal path. Cancellation is a
**control-plane** action: RM *enforces* it; the **Runtime Adapter** (`03`) *performs*
the provider-specific stop; RM never decides what to do *after* cancellation — that is
the future Recovery subsystem.

---

## 1. What cancellation is (and is not)

Cancellation is the deliberate stopping of a session's execution **before its natural
end**, taking it to the terminal state `Cancelled` (`07`) and then, always, to
`Destroyed`. It is RM's expression of one principle: a runtime Nexus started, Nexus can
stop.

> Cancellation answers *"stop this attempt and tear it down."* It does **not** answer
> *"what next?"* — whether to retry, switch runtime, or abort is a Recovery decision
> (`enums.RecoveryBehavior`), made by a **separate later phase**. RM cancels and stops;
> it never selects a recovery verdict.

| Cancellation **is** | Cancellation **is not** |
|---|---|
| A control-plane stop of one session | A re-plan or re-order of work |
| Graceful-first, forced-as-fallback | A guarantee the runtime obeys gracefully |
| Always followed by teardown to `Destroyed` (`07`) | A failure classification (that is `11`) |
| A normalized *intent* RM issues to the adapter | Provider-specific kill mechanics (those live in `03`) |
| Idempotent — a duplicate cancel is a no-op | A retry decision (that is Recovery) |

A timeout firing (`10`) is **not itself** a cancellation; it is a trigger that
*escalates into* one (§4). A typed error (`11`) takes the session to `Failed`, not
`Cancelled`; only an explicit stop-this-attempt action yields `Cancelled`.

## 2. Who initiates cancellation

RM treats every initiator as the same **normalized cancel intent** — they differ only in
*reason*, never in *mechanism*. The reason is recorded on the `runtime.cancelled` event
(`15`).

| Initiator | Origin | Typical reason carried |
|---|---|---|
| **Operator** | A human/control surface requesting stop | operator-requested |
| **Governance** | A policy checkpoint denying continuation (`18`) | policy-denied |
| **Supervisor** | A supervising subsystem recommending `CANCEL` (future; `enums.InterventionRecommendation.CANCEL`) | supervision-recommended |
| **Timeout** | A timeout fired (`10`) and escalated here | timed-out (+ timeout_kind) |
| **RM itself** | Abandoning a session during preparation before handoff (`07`) | preparation-abandoned |

RM **enforces** cancellation from any of these; it does not *evaluate* whether the
reason is justified. Governance decides the policy verdict (`18`); Supervision decides
the recommendation; RM receives the resulting intent and acts. The supervisor and
governance initiators arrive as inputs/events, not as decisions RM makes.

## 3. The two cancellation modes

### 3.1 Graceful cancellation (preferred)

Graceful cancellation **requests** that the runtime stop and **allows it time to clean
up**: flush buffers, close files, finish writing in-progress artifacts, and exit on its
own. The sequence (all provider mechanics behind the adapter, `03`):

```
RM issues normalized "cancel (graceful)" intent
        │
        ▼
Adapter requests stop in the runtime's native idiom
   (e.g. cooperative stop signal / API stop / close-input)
        │
        ▼
Runtime drains: flush streams (08), finish/seal partial artifacts (13),
                emit final progress (12), exit
        │
        ▼
RM observes the stop, runs adapter cleanup (§6), state → Cancelled → Destroyed
```

Graceful cancellation is **bounded**: RM allows a *grace window* (a declarative bound,
sourced like any timeout from the Execution Strategy / policy — `10`, never a number RM
invents). If the runtime stops within the window, the cancel completes gracefully. If it
does not, RM **escalates to forced** (§3.2). The grace window is itself a timeout, so it
shares the timeout machinery of `10`.

### 3.2 Forced cancellation (fallback / last resort)

Forced cancellation is the **hard stop** used when graceful is impossible or has not
taken effect in time:

- the runtime has **no cooperative stop** capability (`05` records it as unsupported);
- the runtime **ignored** the graceful request within the grace window;
- the situation demands an **immediate** stop (e.g. a governance hard-deny, a security
  containment action under `17`).

Forced cancellation **abandons** the drain step. The adapter performs the provider's
hardest available stop (kill the process, stop/remove the container, close the browser,
sever the transport — all behind `03`). Partial artifacts already emitted are still
collected (§7), but no *new* clean shutdown output is expected. RM then runs cleanup
(§6) and reaches `Cancelled → Destroyed`.

| Aspect | Graceful | Forced |
|---|---|---|
| Runtime gets to clean up? | Yes (within grace window) | No |
| In-flight artifacts | Sealed/finished by runtime where possible | Only what was already emitted (`13`) |
| Trigger to use it | Default first attempt | Graceful failed/impossible, or hard-stop required |
| Adapter mechanic | Cooperative stop request (`03`) | Hard kill / teardown (`03`) |
| `runtime.cancelled` payload `mode` | `graceful` | `forced` |
| Terminal state | `Cancelled` → `Destroyed` | `Cancelled` → `Destroyed` |

Both modes converge on the **same** terminal path and the **same** cleanup guarantees;
they differ only in whether the runtime was given a chance to drain.

## 4. Timeout escalation (graceful → forced)

A timeout (`10`) does not bypass the cancellation model — it **enters** it. When any
timeout kind fires, RM emits `runtime.timed_out` (carrying `timeout_kind`) and then
drives cancellation:

```
timeout fires (10)
   │ emit runtime.timed_out { timeout_kind }
   ▼
RM begins GRACEFUL cancel (reason = timed-out)        ── grace window starts
   │
   ├─ runtime stops within grace window ──► runtime.cancelled { mode: graceful }
   │                                          state → Cancelled → Destroyed
   │
   └─ grace window elapses ──► escalate ──► FORCED cancel
                                            runtime.cancelled { mode: forced }
                                            state → Cancelled → Destroyed
```

A timeout-driven cancellation reaches the terminal state along the **same** state path
as any other cancel (§5). Whether the *operation as a whole* is later retried is a
Recovery question — RM only **records** the timeout (`runtime.timed_out`) and the
resulting cancellation, then stops. A timeout is, by canon, a **recoverable failure** to
the future Recovery subsystem (`10`); RM neither retries nor abandons the work on its
own.

> Note on outcome state: a pure timeout that RM resolves by cancelling yields
> `Cancelled`. Where a Strategy/policy instead classifies an elapsed bound as a typed
> error, that path is the Error Model's (`11`) and yields `Failed`. RM follows the
> declared classification; it does not choose between them on its own.

## 5. State path

Cancellation can begin from any non-terminal *execution* state and always lands on
`Cancelled`, then `Destroyed` (`07`):

```
   Running ─┐
   Paused  ─┼──── cancel (graceful or forced) ───► Cancelled ──► Destroyed
   Waiting ─┘                                         │             ▲
                                                      └─────────────┘
                                                   release allocation +
                                                   adapter cleanup (RM, §6)

   Ready ──── pre-start / preparation abandon ──────────────────► Destroyed
              (no Cancelled hop needed for a never-started attempt; 07)
```

- From **Running**: the common case — the engine is performing the Work Package and RM
  stops it.
- From **Paused**: a suspended session can be cancelled outright rather than resumed
  (`07` allows `Paused → Cancelled`).
- From **Waiting**: a session blocked on approval/input (`14`) can be cancelled (e.g. the
  approval was denied or abandoned); `07` allows `Waiting → Cancelled`.
- From **Ready** (before handoff): RM **abandons** the attempt and goes directly to
  `Destroyed` (`07` §3) — there is no running process to stop, so no `Cancelled` hop is
  required.

Every legal source/target here is exactly a transition enumerated in `07` §4. RM invents
no new state and no transition outside that table.

## 6. Cleanup responsibilities (adapter-owned teardown)

Reaching `Destroyed` is **unconditional** for any session that left `Created` (`07` §6).
Cleanup is the adapter's job — RM issues a normalized *teardown intent*; the adapter
performs the provider-specific work, and `17` (security) governs credential/workspace
handling.

| Cleanup duty | Provider examples (behind `03`) | Governed by |
|---|---|---|
| Stop the execution unit | kill process / stop+remove container / close browser / disconnect remote worker | `03` |
| Revoke credentials | invalidate/return the injected credential handle (never logged) | `17` |
| Free the workspace | delete temp dirs, unmount, release the working directory | `13`/`17` |
| Release transport | close sockets/pipes/streams opened for the session (`08`) | `03` |
| Release allocation | return the reservation to `RELEASED` (`ResourceAllocationState`) | `06` |

Order of guarantee: **stop → revoke → free → release allocation → emit terminal events**
(`runtime.released`, then `runtime.destroyed`, `15`). If a cleanup step *itself* fails,
that is recorded as a typed **teardown error** (`11`) — but the session **still** reaches
`Destroyed`; the leak/anomaly is surfaced, never hidden (`07` §6). Cleanup is never
skipped on the forced path; a hard kill still revokes credentials, frees the workspace,
and releases the allocation.

## 7. Partial artifacts on cancel

Cancellation does **not** discard work already produced. Any Evidence Candidate or output
the runtime emitted before the stop (`runtime.artifact_emitted`, `13`) **remains
associated** with the session by reference — it is in the event log, which is the source
of truth (ADR-001), so cancellation cannot retract it.

- **Graceful:** the runtime may *seal/finish* in-progress artifacts during its drain, so
  the partial set is as complete as the grace window allowed.
- **Forced:** only artifacts already emitted survive; in-flight, unsealed output may be
  absent or incomplete.

In both modes RM **collects and references** whatever exists; it never **grades** it.
Whether a partial artifact set is *useful* is a Validation question (Evidence Candidates →
Evidence, INV-20), not RM's, and what to do given a partial result is Recovery's.

## 8. Idempotency

Cancellation is **idempotent** (INV-16). A duplicate cancel for a session already
cancelling — or already in `Cancelled`/`Destroyed` — is a **no-op**: it produces no
second stop, no duplicate `runtime.cancelled`, and no change to the projection. This
follows directly from the event model (`15`): `runtime.cancelled` has a deterministic,
dedupe-keyed identifier, so replaying or re-delivering it folds to the same state.

Consequences:

- Multiple initiators racing to cancel the same session (e.g. operator **and** a timeout)
  resolve to a **single** effective cancellation; the first recorded reason wins, later
  ones are no-ops.
- A graceful cancel that has *already escalated to forced* ignores a late-arriving second
  graceful request — the session is already past that point.
- Re-running cancellation after a crash/replay reproduces the same terminal record, which
  is the basis for crash-recovery of RM itself (`07` §5).

## 9. What RM does **not** do on cancel

- **No retry decision.** RM does not decide to re-attempt the package after a cancel; a
  retry is a *new session* with a new attempt ordinal (`02` §6), and the *decision* to
  create it belongs to Recovery (`enums.RecoveryBehavior`, `enums.RetryBehavior`) — a
  separate later phase. RM is the mechanism for stopping, never the policy for retrying.
- **No rollback/abort selection.** `ABORT`, `RESUME`, `ESCALATE` (`enums.RecoveryBehavior`)
  are Recovery verdicts; RM emits the terminal facts and stops.
- **No silent correction.** A cancel that cannot complete gracefully escalates to forced
  and is *recorded*; it is never quietly downgraded or ignored.

RM's entire contribution to cancellation is: receive the normalized intent, drive
graceful→forced as needed, guarantee adapter cleanup to `Destroyed`, preserve partial
artifacts, and emit the typed `runtime.cancelled` / `runtime.released` /
`runtime.destroyed` facts. Everything downstream of those facts is someone else's
decision.

---

### Cross-references

- `01_RUNTIME_MANAGER.md` — supervision step 13 and teardown step 14 of the pipeline.
- `02_RUNTIME_SESSION.md` — sessions are per-attempt; a retry is a new session.
- `03_RUNTIME_ADAPTERS.md` — provider-specific stop/kill/cleanup mechanics.
- `07_RUNTIME_LIFECYCLE.md` — the `Cancelled` and `Destroyed` states and teardown guarantee.
- `08_STREAMING_MODEL.md` — stream drain/close on cancel.
- `10_TIMEOUT_MODEL.md` — the timeouts that escalate into cancellation.
- `11_ERROR_MODEL.md` — typed errors (incl. teardown errors) and the `Failed` path.
- `13_ARTIFACT_MODEL.md` — partial-artifact collection and Evidence Candidates.
- `14_APPROVAL_CALLBACKS.md` — the `Waiting` state a cancel may interrupt.
- `15_RUNTIME_EVENTS.md` — `runtime.cancelled`, `runtime.timed_out`, `runtime.released`, `runtime.destroyed`.
- `17_RUNTIME_SECURITY.md` — credential revocation and workspace teardown.
- `18_RUNTIME_GOVERNANCE.md` — governance-initiated cancellation.
