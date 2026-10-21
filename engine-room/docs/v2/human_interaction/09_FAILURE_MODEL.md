# Failure Model

Status: Target Architecture (design only)

---

# Purpose

This document defines how Human Interaction behaves under failure — no response, timeout, conflicting
responses, duplicate approvals, disconnected channels, unavailable operators — and fixes **ownership**:
HI owns *interaction-transport* failures; the *meaning* of a failure for the workflow belongs to the
requesting subsystem.

---

# The two ownership halves

> HI owns **reaching the human and collecting a valid answer**. The requester owns **what the absence
> or nature of an answer means for the work.**

| Failure | HI owns (transport) | Requester owns (meaning) |
|---|---|---|
| no response / timeout | emit `interaction.timed_out`; stop waiting | decide abort/escalate/hold (`../19`, `../12`) |
| conflicting responses | resolve deterministically to one settled outcome | act on the settled outcome |
| duplicate approvals | dedupe idempotently (INV-16) | unaffected — sees one decision |
| disconnected channel | retry / fail over / escalate (`10`) | decide if repeated failure blocks the work |
| unavailable operator | reminders, then escalate/time out | decide the consequence of no operator |

HI never decides the workflow consequence; it reports the transport outcome and lets the requester —
which owns the gate and its policy — decide.

---

# No response / timeout — fail-closed, always

The single most important safety property, inherited verbatim from `../runtime/14` §7 and INV-30:

- Every Interaction carries a wait bound from the requester's Strategy/policy (HI enforces, never
  invents — `04`).
- On expiry, HI emits `interaction.timed_out` and **stops waiting**. It **never fabricates an
  answer.**
- For a **governed approval**, absence of a decision is treated as **no privilege granted** — never an
  implicit grant. The enforcing layer (RM/Actuation) takes the fail-closed terminal path
  (`../runtime/14` §7, `../actuation/07`).
- For a **clarification**, a timeout means the requester proceeds under its own low-confidence policy
  (Intent Resolution may abandon; EI may lower autonomy — `../16`, `../engineering/08`).

Safety never depends on a human answering. Silence is the *safe* default (deny/hold), never the
*permissive* one.

---

# Conflicting responses — deterministic settlement

Two answers can arrive for one Interaction (two approvers, a late reply after a timeout, the same
person answering twice differently). Resolution is **deterministic** (INV-16, so replay is stable):

- **First valid settlement wins.** The first Response that *settles* the Interaction (a grant, a
  reject, a valid choice) closes it; later answers are recorded as `interaction.responded` facts but
  do **not** re-open a settled Interaction (immutability, INV-13).
- **`multi_stage` approvals** are not "conflicting": they require *all* stages, and **any reject
  settles as reject** (`../runtime/14` §3) — a deterministic rule, not a race.
- A late reply after a **timeout** does not un-settle the timeout; the Interaction is already
  terminal. (If the requester wants to honor a late answer, it opens a *new* Interaction — the log
  stays append-only.)

Determinism here is essential: the same event stream must always settle to the same outcome, or
replay would diverge (INV-14).

---

# Duplicate approvals — idempotent dedup

A double-click, a channel retry, or an at-least-once redelivery can submit the same decision twice.
HI **dedupes by Interaction/decision identity** (INV-16): the second submission causes no duplicate
state change and no second decision event. The enforcing layer, which also consumes idempotently
(`../runtime/14` §4 step 5), sees exactly one decision. Duplicate approvals cannot double-authorize.

---

# Disconnected channel — retry, fail over, escalate

If a Channel Adapter cannot deliver or loses connection:

```
deliver fails ──► retry (bounded) ──► still failing? ──► fail over to another channel (10)
                                                │                    │
                                                │                    ▼
                                                │            re-deliver on the new channel
                                                ▼
                                        no channel works ──► interaction.escalated / interaction.failed
```

- Fail-over is **channel-independent** by design: the request is answerable on any channel because the
  reply correlates by reference, not by channel (`../runtime/14` §5, `10`).
- Delivery failure is a **transport** fact (`interaction.failed`, `08`); whether repeated delivery
  failure *blocks the work* is the requester's decision.

---

# Unavailable operator — remind, then escalate/time out

If the intended human does not respond:

- HI sends **reminders** before the deadline (`interaction.reminded`, `04`);
- if still unanswered, HI **escalates** to another authority/channel where the request/policy permits
  (`interaction.escalated`), or lets the **timeout** fire (fail-closed above);
- HI never *reassigns authority* on its own beyond what the requester/policy specified — *who may
  answer* is Governance's concern (`11`, INV-29), not HI's.

---

# Failures are recorded, never silent

Every failure path is an event (`08`, INV-31): `timed_out`, `failed`, `escalated`, `cancelled`. A
fail-closed refusal is auditable, never invisible — the same discipline as runtime/actuation
governance (`../runtime/18` §5, `../actuation/07`). An operator can always reconstruct *why* a gated
action did not proceed: because no valid decision arrived in time.

---

# North Star

When a human cannot be reached or does not answer, Human Interaction does the safe thing and says so:
it never invents an approval, it settles conflicts deterministically, it dedupes duplicates, it fails
over channels — and it always hands the workflow's decision back to the subsystem that owns it.
