# Interaction Model

Status: Target Architecture (design only)

---

# Purpose

This document defines the canonical object model of Human Interaction — the objects that represent a
human touchpoint and how they relate.

---

# Five objects

The exercise proposed Interaction, Interaction Request, Interaction Session, Response, Decision. All
five are correct and each has a distinct role:

| Object | Role | Lifetime |
|---|---|---|
| **Interaction** | the durable aggregate record of one touchpoint | created → closed |
| **Interaction Request** | the outbound ask carried by an Interaction | fixed at creation (immutable) |
| **Interaction Session** | a conversation grouping one or more Interactions | long-lived, resumable (`04`) |
| **Response** | the human's inbound reply to a Request | one per answered Interaction (`07`) |
| **Decision** | the settled outcome derived from a Response | terminal for the Interaction (`05`) |

```
Interaction Session (a conversation — 04)
   └─ Interaction (a touchpoint)
        ├─ Interaction Request   (what the human is asked; immutable)
        ├─ Response              (what the human replied; validated — 07)
        └─ Decision              (the settled outcome; for approvals, ADR-004-tagged — 05)
```

---

# Interaction (the aggregate)

An **Interaction** is the durable record of one human touchpoint: its kind (`03`), its requester,
the subject it concerns (by reference — INV-27), its Session, its Request, and its lifecycle state.

- Its **state is a projection of the `interaction.*` event log** (INV-13/14) — created, sent,
  delivered, viewed, responded, timed_out, cancelled, closed (`08`) — never a mutable field bag.
- It is **small and reference-based**: it references the subject (the gated action, the ambiguous
  Goal, the artifact under review) by id; it never embeds the subject's content.
- Its **identifier is deterministic** — a pure function of the originating request's correlation and
  a stable discriminator — so replay yields the same Interaction id and duplicate delivery is
  dedup-keyed (INV-16, mirroring `../runtime/02` §3).

---

# Interaction Request (the outbound ask)

An **Interaction Request** is the immutable specification of what the human is asked. It carries:

- **prompt** — the human-readable question/notice (or a reference to it);
- **subject reference** — what it concerns (INV-27);
- **response schema** — the shape a valid reply must take (`07`): free-text, choice, structured form,
  approval-decision, acknowledgement, or upload-by-reference;
- **approval taxonomy** — for approval kinds, the single platform `ApprovalTaxonomy` value (ADR-004),
  carried opaquely (`05`);
- **deadline / wait bound** — supplied by the requester's Strategy/policy; HI enforces it, never
  invents it (`09`, `../runtime/14` §7);
- **channel preference** — a hint (which channel, which human/role); HI routes, adapters deliver
  (`10`);
- **correlation** — the operation-wide lineage tying this ask to the work that raised it (INV-39).

The Request is fixed at creation. Changing the ask means a *new* Interaction (often in the same
Session, `04`), never mutating the old one — the event log stays the source of truth (INV-13).

---

# Response and Decision (the inbound answer)

- A **Response** is the human's reply, **validated against the Request's response schema** (`07`). It
  is recorded as a `interaction.responded` event carrying the non-deterministic human input as data
  (INV-17). An invalid reply is rejected and re-prompted within the Session (`04`), not silently
  coerced.
- A **Decision** is the settled outcome the requester consumes. For most kinds the Response *is* the
  outcome (a clarification answer, a choice). For **approvals**, the Decision is the grant/reject
  verdict tagged with the ADR-004 `ApprovalTaxonomy`, projected onto the requester exactly as the
  approval callback model expects (`../runtime/14` §4, `05`).

Response and Decision are distinct because one Response may not settle an Interaction (a `multi_stage`
approval needs several — `../runtime/14` §3; a clarification loop needs several rounds — `04`). The
Decision is emitted only when the Interaction is *settled*.

---

# How the model maps to the existing approval contract

The model does not invent a parallel approval representation (INV-07). It **wraps** the existing
contract:

| HI object | Existing platform concept | Source |
|---|---|---|
| approval Interaction | the pending approval a session waits on | `../runtime/14` `approval_ref` |
| Request.approval_taxonomy | the single `ApprovalTaxonomy` | ADR-004 |
| Decision (grant/reject) | the **decision event** the surface produces | `../runtime/14` §4 step 4 |
| correlation/causation | wait-event ↔ decision-event causation | `../runtime/14` §4, INV-39 |

So an approval Interaction *is* the canonical surface's handling of a `runtime.waiting_approval` /
`actuation.approval_requested` event: HI creates the Interaction, delivers it, collects the Response,
and emits the correlated Decision event the pause is waiting for. No new taxonomy, no new decision
type — HI carries the platform's existing ones.

---

# What the model is not

- Not the subject (it *references* the gated action / Goal / artifact).
- Not a policy verdict (the Policy Engine's, INV-28).
- Not an authorization (the approver's, INV-29).
- Not durable operational understanding (Knowledge's, INV-25) — a Response is an event, not a
  learned fact; if a response *should* become learning, that flows through Reflection → Knowledge,
  not HI.

---

# North Star

An Interaction is one honest record of asking a human something and hearing back. Request captures
what was asked, Response what was said, Decision what it settled — each immutable, correlated, and
carrying the platform's existing approval vocabulary rather than a rival one.
