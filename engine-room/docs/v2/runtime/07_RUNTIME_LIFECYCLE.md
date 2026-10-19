# 07 — Runtime Lifecycle

**Status:** design only. Defines the **canonical Runtime Session state machine** — the
states, who drives each transition, and the terminal/teardown guarantees. Every other
document uses these state names verbatim; none may invent a new lifecycle state.

---

## 1. States

| State | Meaning | Driven by | Phase |
|---|---|---|---|
| **Created** | Session exists; package ⇄ runtime binding assigned; not yet configured | RM | preparation |
| **Prepared** | Runtime allocated and configured (env/cwd/limits/isolation rendered) | RM | preparation |
| **Ready** | Fully prepared; eligible for handoff to the Execution Engine | RM | preparation |
| **Running** | The Execution Engine is performing the Work Package inside the runtime | Execution Engine (observed by RM) | execution |
| **Paused** | Execution suspended by control action (e.g. operator/governance), resumable | RM (on signal) | execution |
| **Waiting** | Execution blocked on an external dependency (approval, input, callback) | RM (on `14` callback) | execution |
| **Completed** | The runtime **process** ended normally (work produced; *not yet validated*) | Execution Engine (observed) | terminal |
| **Cancelled** | Execution stopped by cancellation (graceful or forced) before normal end | RM (`09`) | terminal |
| **Failed** | The session ended on a typed error (`11`) | RM (`11`) | terminal |
| **Destroyed** | Allocation released, adapter cleanup run, session closed | RM | teardown |

> **`Completed` means "the process finished," not "the work succeeded."** Real success
> is Validation's verdict from Evidence (INV-20). RM never sets a "validated" state.

## 2. Ownership of transitions

- **RM owns** every transition in **preparation** (`Created → Prepared → Ready`) and
  **teardown** (`* → Destroyed`), plus the control transitions it initiates
  (`Running → Paused`, `→ Waiting`, `→ Cancelled`, `→ Failed`).
- The **Execution Engine drives** `Ready → Running` and the natural ending
  `Running → Completed`; RM **observes** these as reported events and projects them onto
  the session (it does not perform the work that causes them).
- This split is the lifecycle expression of the platform spine: **RM prepares and
  supervises; the engine performs.**

## 3. Transition diagram

```
                 ┌─────────┐
                 │ Created │
                 └────┬────┘
                      │ allocate + configure (RM)
                 ┌────▼─────┐
                 │ Prepared │
                 └────┬─────┘
                      │ readiness checks pass (RM)
                 ┌────▼──┐
                 │ Ready │───────────── handoff ──────────────┐
                 └────┬──┘                                     │
        (engine)      │ start                                  │
                 ┌────▼────┐   pause/resume (RM)   ┌────────┐  │
                 │ Running │◀────────────────────▶ │ Paused │  │
                 └─┬─┬─┬─┬─┘                        └────────┘  │
                   │ │ │ │   block on dependency    ┌─────────┐ │
                   │ │ │ └────────────────────────▶ │ Waiting │ │
                   │ │ │       resume (callback,14)  └────┬────┘ │
                   │ │ │◀─────────────────────────────────┘      │
   normal end ─────┘ │ └───── cancel (09) ─────┐                 │
   ┌───────────┐     │                   ┌─────▼─────┐           │
   │ Completed │     │ error (11)        │ Cancelled │           │
   └─────┬─────┘     │                   └─────┬─────┘           │
         │      ┌────▼───┐                     │                 │
         │      │ Failed │                     │                 │
         │      └────┬───┘                     │                 │
         └───────────┴────────────┬────────────┘                 │
                                  │ release allocation +          │
                                  │ adapter cleanup (RM)          │
                            ┌─────▼─────┐                         │
                            │ Destroyed │◀────── abandon before ──┘
                            └───────────┘        handoff (RM)
```

Notes:
- `Ready` may go directly to `Destroyed` if RM abandons the attempt before handoff
  (e.g. a late policy denial or a cancellation arriving during preparation).
- `Paused` and `Waiting` always return to `Running` or proceed to a terminal state;
  they are never terminal themselves.
- Exactly one of `Completed | Cancelled | Failed` precedes `Destroyed` for any started
  session; a session abandoned during preparation goes `Created/Prepared/Ready →
  Destroyed` directly.

## 4. Legal transitions (table)

| From | Allowed next | Trigger |
|---|---|---|
| Created | Prepared, Failed, Destroyed | configure / intake error / abandon |
| Prepared | Ready, Failed, Destroyed | readiness pass / config error / abandon |
| Ready | Running, Cancelled, Failed, Destroyed | handoff+start / pre-start cancel / error / abandon |
| Running | Paused, Waiting, Completed, Cancelled, Failed | control / dependency / normal end / cancel / error |
| Paused | Running, Cancelled, Failed | resume / cancel / error |
| Waiting | Running, Cancelled, Failed | callback resume (`14`) / cancel / timeout-as-error (`10`) |
| Completed | Destroyed | teardown |
| Cancelled | Destroyed | teardown |
| Failed | Destroyed | teardown |
| Destroyed | — | (terminal) |

Any transition not in this table is **illegal** and must be rejected fail-fast (the
platform's no-silent-correction rule). Illegal-transition rejection mirrors the core
state machine's `IllegalTransitionError` discipline.

## 5. Idempotency & replay

Each transition is recorded as a `runtime.*` event (`15`). Because consumption is
idempotent (INV-16) and the projection is deterministic (ADR-001), replaying a session's
event stream reconstructs the exact same final state — the basis for checkpoints,
crash-recovery of RM itself, and audit.

## 6. Teardown guarantees

`Destroyed` must be reached for **every** session that left `Created`, on every path,
including failure and cancellation:

- the **allocation is released** back to `RELEASED` (`06`) so capacity is never leaked;
- **adapter cleanup** runs (process kill, container removal, temp/workspace teardown,
  credential handle revocation — `17`);
- a terminal `runtime.released` and `runtime.destroyed` event are emitted.

If cleanup itself fails, that is recorded as a typed teardown error (`11`) — the session
still reaches `Destroyed`; the leak/anomaly is surfaced, never hidden.
