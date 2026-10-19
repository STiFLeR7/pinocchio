# Gaps & Deferred Decisions

Status: Target Architecture (design only)

---

# Purpose

An honest enumeration of what is **not yet fully settled** in the Human Interaction architecture. Each
is **known and bounded**: none contradicts the canon (`00`–`12`), the approval model (`../runtime/14`),
or any ADR/contract/invariant, and none blocks a first implementation. Each gap: a 1–2 line statement,
an **urgency** (low/med/high) for *when* it must be settled relative to building HI, and a recommended
direction. This document **modifies no ADR, contract, or invariant**.

---

# G-1 — Approver identity & authorization ("who may answer?")

**Statement.** HI records *who did* answer (`07`) but does not adjudicate *who may* answer a given
approval — that is Governance/Policy (`11`, INV-29). The identity/role model that Governance uses, and
how HI routes to the right authority, is referenced not designed.
**Urgency:** high (an approval answered by the wrong human is a governance hole).
**Direction.** Keep authorization ownership in Governance/Policy Engine; HI routes to the
authority/role the request names and records the answerer's identity for Governance to check. Design
the identity/role model with Governance, not inside HI. Record in `ARCHITECTURE_REVIEW.md`.

---

# G-2 — Should Interaction / Session / Response be FROZEN core contracts?

**Statement.** These are today **HI-layer value objects**, with no frozen `nexus_core` contract —
mirroring the Runtime Session (`../runtime/20` G-1) and actuation objects (`../actuation/13` G-1).
**Urgency:** med.
**Direction.** Keep them as HI-layer value objects for the first implementation; the *decision* event
they carry already conforms to ADR-004 (`05`). Promote to a frozen contract only when a second
subsystem must depend on their shape. Do not pre-freeze.

---

# G-3 — Response schema registry & versioning

**Statement.** `07` fixes a closed set of schema *shapes* but leaves the concrete structured-form
schemas (fields, validation) and their versioning to implementation.
**Urgency:** med.
**Direction.** Treat structured-form schemas as data registered alongside the request (like Policy
data), versioned; HI validates against the declared schema and coins none. A schema registry is an
extension, not a core change.

---

# G-4 — Channel failover & multi-channel delivery policy

**Statement.** `09`/`10` establish failover exists; the policy (which channels, in what order, whether
to fan out to several at once, dedup of a reply arriving on two channels) is specified in shape, not
value.
**Urgency:** med.
**Direction.** Make failover order and fan-out a **request/policy input** (like retry bounds); dedup a
multi-channel reply by interaction reference (INV-16). Calibrate with operational data.

---

# G-5 — Notification deduplication & rate control

**Statement.** High-volume notifications (the v1 briefing firehose) need dedup and rate limits;
`06` defines the kind but not throttling.
**Urgency:** med.
**Direction.** Treat notification throttling as an adapter/delivery concern with a documented policy;
dedup by content+subject reference (INV-16). Lossy notification suppression is acceptable (unlike
governed approvals, which never drop) — log what was suppressed.

---

# G-6 — Long-deferred / asynchronous decisions at scale

**Statement.** `deferred`-taxonomy approvals and parked Sessions (`04`) may wait hours or days; the
persistence, reminder cadence, and expiry policy for many concurrent long waits is not sized.
**Urgency:** med.
**Direction.** Sessions are event-sourced and durable already (`04`); reminder cadence and overall
expiry are Strategy/policy inputs. Capacity of many concurrent waits mirrors the runtime capacity gap
(`../runtime/20` G-3) — a Registry/substrate concern, not HI-owned state.

---

# G-7 — Multi-operator / team routing & escalation chains

**Statement.** The design assumes routing to *an* authority; team inboxes, on-call rotations, and
escalation chains (if A doesn't answer in N minutes, ask B) are named not designed.
**Urgency:** med.
**Direction.** Model an escalation chain as a request/policy input HI enforces mechanically
(reminder → escalate to next authority → timeout); *who is on the chain* is Governance/identity data
(G-1), not HI logic.

---

# G-8 — Interactive-authenticated channel availability in headless runs

**Statement.** Some channels require interactive auth (a logged-in Discord/web session) and may be
absent in headless/cron runs — the same caveat the platform's MCP tooling notes.
**Urgency:** low.
**Direction.** Treat channel availability as Registry health (INV-36); if no interactive channel is
available for a required gate, fail closed (`09`) and fall back to an async channel (email) where the
taxonomy permits `deferred`.

---

# G-9 — Voice / constrained-modality schema limits

**Statement.** Voice and other constrained channels cannot render rich schemas (large forms, uploads);
`10` says they advertise supported schemas, but the fallback when a required schema is unrenderable is
not fully specified.
**Urgency:** low.
**Direction.** HI routes schema-appropriately (`00`); if no available channel can carry a required
schema, treat as a delivery failure (`09`) and escalate/fail-closed. Constrained channels serve
choice/confirm; rich schemas route to web/mobile.

---

# G-10 — Relationship to the v1 communication stack

**Statement.** v1 has a working Discord/email communication layer (`nexus/communication/`). Whether HI
subsumes it, wraps it as adapters, or replaces it is a migration decision, not an architecture one.
**Urgency:** low.
**Direction.** Wrap v1 channels as Channel Adapters (`10`) behind the HI contract; the v1 Dex Discord
integration becomes a Discord adapter. This is a migration path, recorded in
`ARCHITECTURE_REVIEW.md`; it changes no HI architecture.

---

# Gap summary

| ID | Gap | Urgency | Mirrors |
|---|---|---|---|
| G-1 | Approver identity & authorization | high | — |
| G-2 | Freeze Interaction/Session/Response contracts? | med | `../runtime/20` G-1 |
| G-3 | Response schema registry & versioning | med | — |
| G-4 | Channel failover / multi-channel policy | med | — |
| G-5 | Notification dedup & rate control | med | — |
| G-6 | Long-deferred decisions at scale | med | `../runtime/20` G-3 |
| G-7 | Multi-operator / team routing & escalation chains | med | — |
| G-8 | Interactive-auth channels in headless runs | low | — |
| G-9 | Voice / constrained-modality schema limits | low | — |
| G-10 | v1 communication stack migration | low | — |

---

# Why these are not blockers

Every gap sits **inside** the existing seams. None requires a new interaction kind (`03`), a new event
(`08`), or a new dependency direction (`00`). The one high-urgency item (G-1, approver identity) is a
Governance/identity concern HI *consumes*, not owns — it does not reopen HI's architecture, an ADR, a
contract, or an invariant. These are the known edges of a sound design.
