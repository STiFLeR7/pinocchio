# Governance

Status: Target Architecture (design only)

---

# Purpose

This document defines how Human Interaction stays governed, auditable, and safe: it **carries** human
decisions but **evaluates**, **authorizes**, and **decides** none of them. It is the human-facing
counterpart to Runtime Governance (`../runtime/18`) and Actuation Governance (`../actuation/07`).

---

# The posture

> Human Interaction is a **conduit**, never a **decision or authority point**. It carries a request to
> a human and the answer back. It never evaluates policy (INV-28), never authorizes (INV-29), never
> decides an approval, and — when no valid answer arrives — it **fails closed** (INV-30). Every
> interaction is an immutable, correlated audit record (INV-31/39).

This is the same decide-nothing posture that RM holds at an approval checkpoint (`../runtime/14` §1)
and Actuation holds at an action gate (`../actuation/07`), applied to the human-reaching step.

---

# Who decides what (the bright line)

| Concern | Owner | HI's relationship |
|---|---|---|
| Define policies | Governance (`../12`) | none |
| **Evaluate** policy → is approval required? which taxonomy? | Policy Engine (INV-28) | consumes the resolved requirement; never re-evaluates |
| **Authorize** — grant/reject | the approver (INV-29) | records the decision; never makes it |
| Decide *who may* answer a given approval | Governance / Policy Engine | routes to that authority; does not adjudicate eligibility |
| Identify / coordinate gates | Planning / Orchestration | carries the resulting request |
| **Carry the request, collect the response, record it** | **Human Interaction** | this subsystem |

HI *informs* governance by faithfully delivering the request and recording the answer with
attribution; governance *decides*. HI influences no policy and holds no authority — the same relation
Knowledge has to governance ("influences but never evaluates", `../knowledge/ARCHITECTURE_REVIEW.md`).

---

# Fail-closed is the safety spine

Inherited verbatim from `../runtime/14` §7 / `../runtime/18` §6 / INV-30:

- An unanswered approval **never** auto-resolves to "allowed." On timeout HI emits
  `interaction.timed_out` and the enforcing layer takes the fail-closed terminal path (`05`, `09`).
- A missing/ambiguous decision is treated as **no privilege granted**, never an implicit grant.
- Duplicate decisions dedupe idempotently (INV-16); conflicts settle deterministically (`09`).

Human governance is thereby *strengthened*, not bypassed: the platform cannot proceed on a governed
action without a real, recorded human decision — and cannot be tricked into treating silence as
consent.

---

# Human authority remains final

The Vision holds: *"Authority is never autonomous"* (`../12`). HI is the mechanism that keeps a human
in the loop wherever the platform placed a gate:

- Every approval/confirmation/review Interaction is a **real, rejectable** decision point (INV-29).
- Every autonomy gate Engineering Intelligence proposed (`../engineering/08`) and every consequential
  action Actuation flagged (`../actuation/07`) becomes an actual human touchpoint through HI.
- Attribution is recorded — *who* decided, on *which* channel, *when* (INV-31, `07`) — so
  accountability is never anonymous.

HI is what turns "a human must approve this" from an architectural intention into an enforced,
audited event.

---

# Auditability (INV-31) and correlation (INV-39)

Every interaction — created, delivered, viewed, reminded, answered, timed-out, escalated, closed — is
an immutable event (`08`). Because decision/response events carry causation to the originating gate
event (`../runtime/14` §4), governance gets an unbroken lineage:

```
Goal → … → gate identified (Planning) → required (Policy Engine) → pause (RM/Actuation)
     → interaction.created → delivered → interaction.responded (who, which channel, what)
     → decision projected → work resumes or fails closed
```

An auditor can answer *"who authorized this commit, when, and through what channel?"* entirely from
the log — the human-in-the-loop record the platform previously could not produce.

---

# How Engineering Intelligence uses HI under governance

EI's design discussions, reviews, and clarifications (`../engineering/`, and `04`) run through HI
under the same posture:

- EI **decides** it needs an operator (low-confidence Goal, an autonomy gate, a design choice); HI
  **carries** the exchange.
- The operator's answer is a **recorded input** to EI's Engineering Strategy (INV-17), not a Knowledge
  write — no second learning path (INV-25/26).
- Where EI proposes an autonomy gate (`../engineering/08`), HI is the surface that enacts the human
  approval at that gate — closing the loop the Engineering Intelligence review left open
  (`../engineering/14` G10).

---

# Governance boundary summary

| Human Interaction | Enforced by |
|---|---|
| ✓ carries requests and responses | own responsibility |
| ✓ records every interaction with attribution | INV-31 |
| ✓ fails closed on no/ambiguous answer | INV-30 |
| ✓ carries the single ApprovalTaxonomy, opaquely | ADR-004 |
| ✗ never evaluates policy | Policy Engine (INV-28) |
| ✗ never authorizes / decides an approval | the approver (INV-29) |
| ✗ never adjudicates who may answer | Governance |
| ✗ never writes Knowledge | Knowledge Engine (INV-25) |

---

# North Star

Human Interaction is where human authority is exercised, recorded, and kept final — a governed conduit
that makes every "a human must decide this" real, attributed, and impossible to satisfy with silence.
