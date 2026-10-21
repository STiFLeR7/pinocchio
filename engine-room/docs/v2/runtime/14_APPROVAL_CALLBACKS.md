# 14 — Approval Callbacks

**Status:** design only. Defines how the Runtime Manager **pauses a Runtime Session
for human approval, governance, or external authorization** — and resumes it — using
**events and references**, without depending on any UI. RM is a checkpoint/pause
mechanism here; it **never decides an approval** and **never evaluates a policy
verdict**. The decision is always the approver's.

---

## 1. The one rule, stated first

> **RM pauses; it does not decide.** When governance requires it, RM holds a Runtime
> Session at a checkpoint, records that a pause occurred, and waits for a *decision
> event* produced by some external surface. RM **records** the decision; it does not
> **make** it. This is the runtime-layer expression of ADR-004 and of the platform
> spine (`01` §3): RM prepares and supervises; it never becomes an authority.

What RM is forbidden to do at an approval point:

| RM never… | Owner of that act |
|---|---|
| evaluates whether a policy is satisfied | Policy Engine (`18`, INV-28) |
| decides *which* nodes are gated | Planning (records gates); Orchestration (settles them) |
| grants or rejects an approval | the approver (any human/automated authority) |
| invents an approval taxonomy | ADR-004 — single `ApprovalTaxonomy` |
| couples to a specific UI to ask/answer | any surface, via events only (§5) |

RM's only job: **enforce the pause at the runtime boundary where it is required, then
project the externally-supplied decision onto the session's lifecycle.**

## 2. Two places an approval can pause a session

An approval can interrupt a session at exactly two well-defined points. Both reuse the
same event-driven model (§4) and the same lifecycle (`07`).

| # | Checkpoint | When | Lifecycle effect |
|---|---|---|---|
| 1 | **Pre-execution approval checkpoint** | Pipeline step 6 (`01`), *before* SELECT/ALLOCATE, when the resolved policy bundle for this package demands approval before a runtime may be committed | session is still in **preparation** (`Created`/`Prepared`); RM holds before allocation, may abandon to `Destroyed` on reject without ever allocating |
| 2 | **Mid-execution approval** | While the Execution Engine is performing the Work Package and the runtime (through its adapter) **requests authorization to proceed** with a gated action | session is **Running** → moves to **Waiting**; on grant returns to **Running**, on reject proceeds to a terminal state |

Both are *checkpoints*, not authorities. Checkpoint 1 ties to `06` (selection) and
`18` (governance pipeline): RM enforces the pause that the resolved policy bundle
requires before privilege (an allocated runtime) is granted — the fail-closed posture
of `18`. Checkpoint 2 is a runtime requesting permission mid-flight; RM relays the
request as an event and blocks the session until a decision arrives.

> RM does not *originate* the requirement to approve. Checkpoint 1's requirement comes
> from the policy bundle the Harness already resolved (a `require_approval`
> `PolicyDecision`, `18`); checkpoint 2's comes from the runtime/adapter surfacing a
> gated action. RM only **enforces the resulting pause**.

## 3. ApprovalTaxonomy mapping (ADR-004)

RM reads the single platform `ApprovalTaxonomy` carried alongside the gate (on the
Execution Strategy's approval policy, exactly as Orchestration carries it —
`nexus_orchestration/approvals.py`). The taxonomy decides the **wait semantics**, never
the outcome.

```
ApprovalTaxonomy        RM behavior at the checkpoint
----------------------  --------------------------------------------------------------
automatic               NO PAUSE. The gate is pre-settled (granted); RM proceeds
                        directly. No runtime.waiting_approval is emitted.
human_review            PAUSE → Waiting. Block for a single human decision event.
multi_stage            PAUSE → Waiting. Block until ALL required stages have produced
                        their decision events; any stage rejection ends the wait as a
                        rejection. RM counts stages; it does not define them.
deferred                PAUSE → Waiting. Block; the decision is expected later (out of
                        band, possibly long). Subject to approval timeout (§7).
```

Key consequences:

- `automatic` ⇒ no `Waiting` transition, no approval event, no surface involved.
- `human_review` / `multi_stage` / `deferred` ⇒ the session enters **Waiting** (`07`)
  and a `runtime.waiting_approval` event is emitted carrying an **approval reference**
  and the **taxonomy** (`15`).
- RM treats the taxonomy as opaque wait-shape metadata. It never maps a taxonomy to a
  verdict; it only maps it to *how long / how many decisions* it waits for.

## 4. The event-driven callback model

Approval is requested and answered through **events + correlation/causation
references** (`15` §3), never through a coupled call into a UI. The full callback loop:

```
1. RM reaches an approval checkpoint requiring a pause (taxonomy ≠ automatic).
2. RM transitions the session to Waiting and emits:
        runtime.waiting_approval { session, approval_ref, taxonomy }
   The approval_ref is the correlatable handle for the pending decision.
3. SOME SURFACE (Discord / web / CLI / API — any of them, RM is agnostic) observes
   the event, presents it to the appropriate authority, and collects a decision.
4. The surface submits the decision, which enters the platform as a DECISION EVENT
   carrying causation = the runtime.waiting_approval event's id (cause→effect chain).
5. RM consumes the decision event (idempotently, INV-16) and projects it:
        grant    → runtime.resumed { from_state: Waiting }  → Running
        reject   → terminal path (Cancelled or Failed)      → … → Destroyed
6. The decision is RECORDED on the session as an immutable fact; RM made no decision.
```

The decision event is **not** an RM-authored fact. RM authors `runtime.waiting_approval`
(the pause) and `runtime.resumed` / the terminal events (its own lifecycle
transitions). The *decision itself* originates outside RM and arrives as an event RM
merely reacts to — preserving INV-28 (RM hardcodes no governance) and ADR-004 (the
approver decides).

> **Without depending on UI.** The `runtime.waiting_approval` event and its
> `approval_ref` are the entire contract. Any surface that can observe the event and
> emit a correlated decision event satisfies it. RM has no knowledge of, and no
> dependency on, which surface that is.

## 5. Surface-agnosticism

Every surface is equal and interchangeable. RM's behavior is identical regardless of
who answers.

```
                 ┌──────────────────────────────────────────────┐
                 │            runtime.waiting_approval            │
                 │      { session, approval_ref, taxonomy }       │
                 └───────┬───────────┬───────────┬───────────┬────┘
                         │           │           │           │
                    ┌────▼───┐  ┌────▼───┐  ┌────▼───┐  ┌────▼───┐
                    │Discord │  │  Web   │  │  CLI   │  │  API   │
                    └────┬───┘  └────┬───┘  └────┬───┘  └────┬───┘
                         │           │           │           │
                         └───────────┴─────┬─────┴───────────┘
                                           │  decision event
                                           │  (causation = the
                                           │   waiting_approval id)
                                  ┌────────▼─────────┐
                                  │  RM projects it  │
                                  │  resume | terminal│
                                  └──────────────────┘
```

- RM emits **one** event shape regardless of surface.
- A surface is just an event consumer that produces a correlated decision event.
- Adding a surface (or removing one) requires **no change to RM** — the same
  surface-agnostic discipline as the rest of the platform.
- No surface can write RM session state directly; it can only emit a decision event,
  which RM consumes one-way (`15` §5).

## 6. Alignment with Orchestration's existing approval coordination

Orchestration already coordinates approval **gates** (`nexus_orchestration/approvals.py`,
PHASE_5 §4). RM **aligns with and enforces**, it does not duplicate or re-decide.

| Layer | What it does with approval | Document |
|---|---|---|
| Planning | *Identifies* gates (graph `approval` constraints + `policies['approval_gates']`) | PHASE_5 |
| Orchestration | *Coordinates* gates: assigns each gated node the `ApprovalTaxonomy` and a deterministic decision state (automatic ⇒ granted; otherwise requested; out-of-band rejection ⇒ blocked) | `nexus_orchestration/approvals.py` |
| **Runtime Manager** | *Enforces the pause at runtime* where a gate is still unsettled or a runtime requests mid-execution authorization; records the externally-supplied decision | this doc |

Concretely:

- A gate Orchestration already **settled as granted** (e.g. `automatic`, or an
  out-of-band grant) arrives at RM pre-settled — RM does **not** re-open it and does
  **not** pause. RM honors the settled state.
- A gate that is still **requested/pending** when execution reaches it is where RM's
  pause applies: RM holds the session in `Waiting` and surfaces it via
  `runtime.waiting_approval` until a decision event arrives.
- A gate Orchestration recorded as **rejected** never reaches a running runtime; if a
  rejection arrives while RM holds the session, RM takes the terminal path.

> RM never re-evaluates Orchestration's gate logic. It reads the settled state and the
> taxonomy and enforces the consequence at the runtime boundary. There is exactly one
> approval taxonomy across all three layers (ADR-004).

## 7. Approval timeout (ties to `10`)

A `Waiting`-on-approval session is not waited on forever. The approval wait is itself
subject to a timeout (`10`):

- The Execution Strategy / policy supplies the wait bound (RM does not invent it).
- If no decision event arrives within the bound, RM emits `runtime.timed_out`
  (`timeout_kind = approval`, `15`) and takes the **terminal** path — the waiting
  approval becomes a typed timeout error (`11`), not a silent default and not an
  implicit grant.
- This is fail-closed: an unanswered approval **never** auto-resolves to "allowed."
  Absence of a decision is treated as no privilege granted, consistent with `18`.
- `deferred` taxonomy typically carries a longer bound than `human_review`, but the
  mechanism is identical — RM only enforces the bound it was given.

## 8. Lifecycle & sequence

### 8.1 State view (uses `07` states verbatim)

```
  ┌─────────┐  taxonomy == automatic (no pause)   ┌─────────┐
  │ Running │ ──────────────────────────────────▶ │ Running │  (proceeds)
  └────┬────┘                                      └─────────┘
       │  approval checkpoint, taxonomy ≠ automatic
       │  emit runtime.waiting_approval
  ┌────▼────┐
  │ Waiting │
  └────┬────┘
       │
       ├── decision event = GRANT ───▶ runtime.resumed ───▶ Running
       │
       ├── decision event = REJECT ──▶ Cancelled | Failed ─▶ … ─▶ Destroyed
       │
       └── approval timeout (10) ────▶ runtime.timed_out ──▶ Failed ─▶ Destroyed
```

(For the **pre-execution** checkpoint, the same shape applies before allocation: a
reject/timeout abandons the attempt `Created/Prepared → Destroyed` per `07` §3, having
never allocated a runtime — fail-closed, no privilege escalation.)

### 8.2 Sequence (mid-execution approval)

```
Runtime/Adapter      RM                    Event Log              Surface (any)
     │                │                        │                       │
     │ request auth   │                        │                       │
     ├───────────────▶│ pause → Waiting        │                       │
     │                ├─ runtime.waiting_approval ──────────────▶       │
     │                │  {approval_ref,taxonomy}│                       │
     │                │                        │  observe event ──────▶ │
     │                │                        │                       │ present to
     │                │                        │                       │ approver
     │                │                        │  ◀── decision event ───┤ (grant/reject)
     │                │ ◀── consume (INV-16) ───┤ causation = wait id    │
     │                │                        │                       │
     │  GRANT path:   │ runtime.resumed ──────▶│                       │
     │ ◀──────────────┤ resume → Running        │                       │
     │  proceed       │                        │                       │
     │                │                        │                       │
     │  REJECT path:  │ → Cancelled|Failed ───▶│                       │
     │ ◀── stop ──────┤ → released → destroyed  │                       │
```

## 9. What RM records vs. what RM decides

| Fact on the session | Authored by | RM's role |
|---|---|---|
| "a pause occurred at this checkpoint" | RM | RM authors (`runtime.waiting_approval`) |
| the approval taxonomy in effect | ADR-004 / Strategy | RM carries it through, opaque |
| **the grant/reject decision** | **the approver (external)** | **RM records it; never makes it** |
| "session resumed" / terminal transition | RM | RM authors its own lifecycle move |
| the audit trail linking all of the above | the event log (`15`, INV-39) | RM emits; never edits |

The decision belongs to the approver. RM's contribution is the *pause*, the
*surface-agnostic request*, and the *faithful projection* of whatever decision the
log delivers.

## 10. Cross-references

- `01` §4 step 6 — the **approval checkpoint** in the preparation pipeline.
- `06` — selection/allocation, which the pre-execution checkpoint guards.
- `07` — `Waiting` state, `runtime.resumed`, and terminal/teardown transitions.
- `10` — approval-wait **timeout** semantics.
- `15` — `runtime.waiting_approval` / `runtime.resumed` events; correlation/causation.
- `18` — governance: where `require_approval` (`PolicyDecision`) routes here, and the
  fail-closed posture this document enforces at the runtime boundary.
- `nexus_orchestration/approvals.py` / PHASE_5 §4 — the gate coordination RM aligns with.
- ADR-004 — the single `ApprovalTaxonomy` and closed `PolicyDecision` set.
