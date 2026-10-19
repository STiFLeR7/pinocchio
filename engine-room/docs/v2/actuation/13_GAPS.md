# Gaps & Deferred Decisions

Status: Target Architecture (design only)

---

# Purpose

An honest enumeration of what is **not yet fully settled** in the Execution Actuation architecture.
Each is **known and bounded**: none contradicts the canon (`00`–`12`) or the Runtime/Execution/
Recovery architectures, and none blocks a first implementation. Listing them keeps a future team from
rediscovering them as surprises. This document **modifies no ADR, contract, or invariant**; where a
clarification is recommended, it points to `ARCHITECTURE_REVIEW.md`.

Each gap: a 1–2 line statement, an **urgency** (low/med/high) for *when* it must be settled relative
to building Actuation, and a recommended direction.

---

# G-1 — Should Environment / Workspace / Session be FROZEN core contracts?

**Statement.** These are today **actuation-layer value objects**, with no frozen `nexus_core`
contract — mirroring how the Runtime Session is a runtime-layer output (`../runtime/20` G-1,
Phase-5 O-7).
**Urgency:** med.
**Direction.** Keep them as actuation-layer value objects for the first implementation; promote to a
frozen contract only when a *second* subsystem must depend on their shape. Record in
`ARCHITECTURE_REVIEW.md`; do not pre-freeze.

---

# G-2 — Relationship of the actuation Session to the Runtime Session, formalized

**Statement.** `04` fixes that one long-lived actuation Session may serve multiple per-attempt Runtime
Sessions (reattach). The exact reference/ownership handshake at the adapter boundary is specified in
prose, not in a contract.
**Urgency:** high (it is the load-bearing new relationship; ambiguity here confuses ownership).
**Direction.** Do not change `../runtime/02`. Formalize the seam in `ARCHITECTURE_REVIEW.md`: the
Runtime Session references the actuation Session by id via the adapter; Actuation owns the Session
lifecycle; RM owns the binding. Confirm the reattach handshake when the Execution Engine phase lands.

---

# G-3 — Secrets Broker

**Statement.** `11` establishes Actuation holds only secret *references* resolved from `.env`. A
dedicated **Secrets Broker** that mediates resolution/rotation/scoping is named but not designed.
**Urgency:** med.
**Direction.** Keep `.env` as the single source (`../runtime/17` §1) for the first implementation;
inject references at configure-time. A Broker is a later mediation layer that preserves the same
"references only, values never stored by Actuation" property — additive, no core change.

---

# G-4 — Concurrency / capacity of Environments and Sessions

**Statement.** How many concurrent Sessions an Environment (or a single provider) may host, and
pooling/quotas, is flagged not designed — the same open question as runtime capacity
(`../runtime/20` G-3).
**Urgency:** high (real use needs back-pressure to avoid over-provisioning environments).
**Direction.** Treat capacity as a Registry/availability concern (INV-36); model
one-Session-per-Environment conservatively until a capacity model (shared with `../runtime/20` G-3)
lands. Do not invent Actuation-owned capacity state.

---

# G-5 — Resume depth per environment kind

**Statement.** `04`/`10` make resume expressible, but which kinds genuinely resume (vs only restart)
differs sharply — a stateless `terminal` cannot resume; a container or CLI may (`../runtime/20` G-4).
**Urgency:** med.
**Direction.** Make resume an **Actuator-declared capability** advertised in the descriptor; expose
the checkpoint reference only to capable actuators, else restart cold. Recovery decides *use*;
Actuation is the mechanism.

---

# G-6 — The reattach window policy

**Statement.** `10` introduces a bounded reattach window for kept-alive `Detached` Sessions. The
policy for its duration, and who sets it (Strategy? Recovery? Governance?), is specified in shape,
not value.
**Urgency:** med.
**Direction.** Make the window a **Strategy/Recovery input** (like retry bounds, `../19`), enforced
by Actuation as a mechanism; a lapsed window triggers teardown (`09`/`11`). Calibrate with
operational data.

---

# G-7 — Streaming backpressure & retention for `actuation.output`

**Statement.** The fine-grained action stream can out-produce its sink; retention/backpressure limits
are not bounded (mirrors `../runtime/20` G-5).
**Urgency:** med.
**Direction.** Define `actuation.output` as bounded/throttleable with a documented retention limit;
treat dropped *stream* samples as lossy-not-corrupting, since anything that matters is also captured
as a referenced Evidence Candidate (`08`). Persistence depth is a Phase-2-substrate tuning decision.

---

# G-8 — Cost accounting for real actuation

**Statement.** Real environments incur real cost (compute minutes, API usage, runner time). Where
authoritative cost figures enter (Actuator-reported usage events vs derived metrics) is undecided
(mirrors `../runtime/20` G-8).
**Urgency:** med.
**Direction.** Cost must enter as **events** on the `actuation.*` log (Actuator-reported usage),
never as observability metrics, so it is auditable and replayable; define the cost-event source
before enforcing any hard ceiling.

---

# G-9 — Human-interaction channel for approval gates

**Statement.** `07` places approval gates and Actuation enacts the pause, but the *channel* through
which a human grants/rejects a gated action (and answers clarifications) is platform-wide and not
Actuation's — the same seam Engineering Intelligence named (`../engineering/14` G10).
**Urgency:** high (without a channel, gated autonomy cannot complete unattended work).
**Direction.** Actuation only *marks and pauses*; enacting the interaction is Orchestration's/
Governance's behind whatever Human-Interaction subsystem the platform later provides. Co-design that
subsystem next; it is shared, not Actuation-specific.

---

# G-10 — Multi-node / distributed actuation

**Statement.** The design assumes a single logical actuation control plane; running environments
across many hosts/clusters with consistent session ownership is not designed (mirrors
`../runtime/20` G-6).
**Urgency:** low (single-node suffices for the first implementation).
**Direction.** Lean on deterministic ids and idempotent event consumption (INV-16); distributed
actuation is a later consistency problem over the same log, not a redesign.

---

# Gap summary

| ID | Gap | Urgency | Mirrors |
|---|---|---|---|
| G-1 | Freeze Environment/Workspace/Session as core contracts? | med | `../runtime/20` G-1 |
| G-2 | Actuation Session ↔ Runtime Session seam, formalized | high | — |
| G-3 | Secrets Broker | med | — |
| G-4 | Concurrency / capacity | high | `../runtime/20` G-3 |
| G-5 | Resume depth per kind | med | `../runtime/20` G-4 |
| G-6 | Reattach window policy | med | — |
| G-7 | `actuation.output` backpressure/retention | med | `../runtime/20` G-5 |
| G-8 | Cost accounting source | med | `../runtime/20` G-8 |
| G-9 | Human-interaction channel for approvals | high | `../engineering/14` G10 |
| G-10 | Multi-node / distributed actuation | low | `../runtime/20` G-6 |

---

# Why these are not blockers

Every gap sits **inside** the existing seams, not across them. None requires a new lifecycle state
(`03`/`04`), a new event (`08`), or a new dependency direction (`00`). The high-urgency items are a
seam formalization (G-2), a capacity extension shared with the Runtime layer (G-4), and a
platform-wide human-interaction subsystem (G-9) — none reopens an ADR, contract, or invariant. These
are the known edges of a sound design.
