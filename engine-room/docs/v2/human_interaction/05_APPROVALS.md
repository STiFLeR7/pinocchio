# Approvals

Status: Target Architecture (design only)

---

# Purpose

This document defines how approvals integrate — and answers the exercise's central question:

> Should every subsystem implement approvals, or delegate?

**Delegate.** Every subsystem's approval *delegates the human-reaching to Human Interaction*, while
keeping its own decision authority. HI is the canonical surface the existing approval model already
delegates to (`../runtime/14` §4–5); it decides no approval, evaluates no policy, authorizes nothing.

---

# The approval chain, and where HI fits

Approvals already have a complete, layered chain. HI does not replace any link; it fills the one that
was hand-waved — "some surface presents this to a human and collects a decision" (`../runtime/14`
§4).

```
Planning          IDENTIFIES gates            (graph approval constraints; policies['approval_gates'])
   │
Policy Engine     DECIDES required + taxonomy  (require_approval PolicyDecision + ApprovalTaxonomy — INV-28, ADR-004)
   │
Orchestration     COORDINATES gates            (assigns taxonomy + decision state — nexus_orchestration/approvals.py)
   │
Runtime / Actuation ENFORCES the pause         (waits at the boundary — ../runtime/14, ../actuation/07)
   │
   │  emits: runtime.waiting_approval / actuation.approval_requested { approval_ref, taxonomy }
   ▼
[ Human Interaction ]  IS THE SURFACE          ← presents to the approver, collects the decision (../runtime/14 §4 step 3)
   │
   │  emits: correlated DECISION event (grant/reject, causation = the wait event)
   ▼
Runtime / Actuation  PROJECTS the decision      (resume on grant; terminal on reject — ../runtime/14 §4 step 5)
   │
the approver      MADE the decision            (any human authority — INV-29)
```

HI occupies exactly the "surface" slot. Everything above and below is unchanged.

---

# Delegate the reaching, keep the authority

The division that makes this safe:

| Concern | Owner | HI's role |
|---|---|---|
| identify approval gates | Planning | none |
| decide approval is required + taxonomy | Policy Engine (INV-28) | none |
| coordinate gates, assign taxonomy/state | Orchestration | none |
| enforce the pause at the boundary | Runtime Mgr / Actuation | none |
| **present the request to a human, collect the decision** | **Human Interaction** | **this subsystem** |
| **make** the grant/reject decision | the approver (INV-29) | records it; never makes it |
| project the decision onto the flow | Runtime Mgr / Actuation | none |

So no subsystem implements its own way to reach a human for approval; they all **delegate the
reaching** to HI. But none delegates the *authority* — the approver still decides, the Policy Engine
still evaluates, the enforcing layer still projects. HI is a conduit, not a decision point — the same
posture RM holds (`../runtime/14` §1: "RM pauses; it does not decide").

---

# HI carries the single ApprovalTaxonomy — it invents none

An approval Interaction carries the platform's **single `ApprovalTaxonomy`** (ADR-004), opaquely
(`02`, `03`). HI maps the taxonomy only to *wait shape*, never to an outcome — exactly as RM does
(`../runtime/14` §3):

| `ApprovalTaxonomy` | HI behavior |
|---|---|
| `automatic` | no Interaction is created — the gate is pre-settled; HI is not involved |
| `human_review` | one Interaction; await a single decision |
| `multi_stage` | one Session of several Interactions; await all required stages; any reject settles as reject |
| `deferred` | one Interaction with a long wait bound; the decision is expected out-of-band later (`04`) |

HI never maps a taxonomy to grant/reject; it maps it to *how many decisions / how long to wait*. The
outcome is always the approver's.

---

# The Decision event HI emits

When an approval Interaction settles, HI emits the **decision event** the enforcing layer is waiting
for (`../runtime/14` §4 step 4), carrying:

- the **grant/reject** verdict (the approver's, INV-29);
- **causation = the originating** `runtime.waiting_approval` / `actuation.approval_requested` event
  (so "who authorized what" is reconstructable — `../runtime/14` §4, INV-39);
- an **approval reference** matching the pending pause;
- the recording of *who* answered on *which channel* (audit, `11`, INV-31).

The enforcing layer consumes it idempotently (INV-16) and projects it: grant → resume; reject →
terminal (`../runtime/14` §4 step 5). HI authored the *surfacing* and the *faithful projection of the
decision*; it authored no decision.

---

# One surface for every subsystem's approvals

Because HI is the canonical surface, every approval-raising subsystem uses the **same** mechanism:

| Subsystem | Its approval need | Delegates to HI as |
|---|---|---|
| **Execution Actuation** | commit to shared branch, push, deploy, destructive delete, external message (`../actuation/07`) | an `approval` Interaction on the gated action |
| **Runtime Manager** | pre-execution / mid-execution runtime authorization (`../runtime/14`) | an `approval` Interaction on the runtime pause |
| **Recovery** | human review of a recovery path (`../19`) | an `approval`/`escalation` Interaction |
| **Engineering Intelligence** | operator sign-off on an autonomy gate (`../engineering/08`) | an `approval`/`review` Interaction |
| **Governance** | high-risk authorization (`../12_GOVERNANCE.md`) | an `approval` Interaction |

Each keeps its own gate logic and decision authority; each reaches the human the same way. This is
the consolidation the reviews called for: one surface, many delegating subsystems, zero duplicated
approval transports.

---

# Fail-closed (the safety property)

An approval Interaction that is **not answered** never becomes an implicit grant (INV-30,
`../runtime/14` §7): on timeout HI emits `interaction.timed_out`, and the enforcing layer takes the
fail-closed terminal path — the absence of a decision is treated as *no privilege granted*, never as
"allowed." Duplicate decisions are deduped idempotently (INV-16); conflicting decisions resolve
deterministically (`09`). Safety never depends on a human answering.

---

# North Star

Approvals were always meant to be answered by "some surface." Human Interaction is that surface, made
canonical — one place every subsystem reaches a human for a decision, carrying the platform's single
taxonomy, recording who decided, and never deciding itself.
