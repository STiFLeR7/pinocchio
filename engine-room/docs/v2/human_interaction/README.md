# Nexus v2 — Human Interaction Architecture (design only)

> **Status:** Architecture & design specification. **No implementation.** This directory defines
> *what* the Human Interaction subsystem is and *how* it must behave, so a future team can build it
> without making new architectural decisions. It introduces **no** production code, Protocols,
> classes, algorithms, or APIs. It amends **no** ADR, contract, or invariant; where the existing
> architecture needs clarification, that is recorded as a *recommendation* in
> [`ARCHITECTURE_REVIEW.md`](ARCHITECTURE_REVIEW.md), not applied. It specifies the **canonical
> "surface"** that the existing approval model (`../runtime/14_APPROVAL_CALLBACKS.md` §4–5) and the
> actuation approval gate (`../actuation/07_GOVERNANCE.md`) already delegate to; it never contradicts
> them.

## Why this exists

Every architecture review since Runtime converges on the same missing piece. The approval model is
already surface-agnostic *by design*:

> *"SOME SURFACE (Discord / web / CLI / API — any of them, RM is agnostic) observes the event,
> presents it to the appropriate authority, and collects a decision."* — `../runtime/14` §4
> *"A surface is just an event consumer that produces a correlated decision event. Adding a surface
> requires no change to RM."* — `../runtime/14` §5

That "surface" has never been given a canonical home. Meanwhile clarifications (Intent Resolution
`../16`, Engineering Intelligence `../engineering/08`), approval gates (Actuation
`../actuation/07`, Runtime `../runtime/14`), escalations (Recovery `../19`, Supervision `../09`), and
notifications each *assume* a way to reach a human, but none owns the mechanics of doing so. If each
subsystem built its own, the platform would have many inconsistent, separately-audited ways to talk
to a person.

**Human Interaction is that surface, specified once.** It is the single, provider-independent
subsystem that carries any human touchpoint — presents the request through a channel, collects a
structured response, manages the conversation, handles timeout/duplicate/disconnect, and emits the
correlated decision/response event the requesting subsystem already knows how to consume. It answers
exactly one question:

> When any subsystem needs a human — to approve, clarify, confirm, review, be notified, or decide —
> **how is that human reached, presented the request, and their response collected and returned** —
> deterministically, auditably, across any channel, **without Human Interaction ever deciding the
> approval, evaluating a policy, or authorizing anything?**

**Subsystems decide *what* to ask a human and *what the answer means*. Human Interaction owns *the
asking* — reaching the human and carrying the answer back.** That sentence is the spine of every
document here.

## The clean framing: the Harness for the human

Nexus already integrates every external *system* through a Harness (`../11_HARNESS.md`), every
external *engineering environment* through Actuation (`../actuation/`). Human Interaction is the
same idea for the one "external system" that is a **person**: the integration boundary for humans,
provider-independent, whose channels (Discord, Slack, email, CLI, web, Teams, mobile, voice) are
**channel adapters** — exactly as runtimes and actuators are adapters. It unifies what
`../11_HARNESS.md` scattered across "Human Operator" (runtime) and "Human Approval" (governance) into
one interaction-lifecycle subsystem.

## What Human Interaction is NOT

| Concern | Owner — **not** Human Interaction |
|---|---|
| Understand the request; normalize intent; *decide* to ask for clarification | Intent Resolution (`../16`) / the requesting subsystem |
| Decide the engineering approach; *decide* a design question needs an operator | Engineering Intelligence (`../engineering/`) |
| Identify approval **gates** | Planning |
| **Coordinate** approval gates (assign taxonomy + decision state) | Orchestration (`nexus_orchestration/approvals.py`) |
| **Evaluate** policy / decide approval is required | Policy Engine (ADR-004, INV-28) |
| **Authorize** — make the grant/reject decision | Governance / **the approver** (INV-29) |
| **Enforce** the pause at the runtime/actuation boundary | Runtime Mgr (`../runtime/14`) / Actuation (`../actuation/07`) |
| Observe/inspect operations read-only | Operator Experience (`../runtime/operator`) |
| Know provider APIs (Discord/SMTP…) | Channel Adapters (`10`), not the HI core |

Human Interaction **carries** interactions. It decides none of the above.

## Reading order

| # | Document | Defines |
|---|---|---|
| — | [`00_OVERVIEW.md`](00_OVERVIEW.md) | The subsystem, cross-cutting placement, inputs/outputs, dependency direction, canon glossary |
| — | [`01_HUMAN_INTERACTION.md`](01_HUMAN_INTERACTION.md) | Responsibilities, the deliver→collect pipeline, the "carry, never decide" discipline |
| — | [`02_INTERACTION_MODEL.md`](02_INTERACTION_MODEL.md) | The object model: Interaction, Interaction Request, Interaction Session, Response, Decision |
| — | [`03_INTERACTION_TYPES.md`](03_INTERACTION_TYPES.md) | The closed set of interaction kinds and the completeness argument |
| — | [`04_CONVERSATIONS.md`](04_CONVERSATIONS.md) | Multi-exchange sessions, clarification loops, timeouts, resume, history |
| — | [`05_APPROVALS.md`](05_APPROVALS.md) | How HI is the canonical surface every subsystem's approvals delegate to |
| — | [`06_NOTIFICATIONS.md`](06_NOTIFICATIONS.md) | One-way interactions; delivery/view; acknowledgement |
| — | [`07_RESPONSES.md`](07_RESPONSES.md) | The canonical response model and response schemas |
| — | [`08_EVENT_MODEL.md`](08_EVENT_MODEL.md) | The canonical `interaction.*` event taxonomy |
| — | [`09_FAILURE_MODEL.md`](09_FAILURE_MODEL.md) | No response, timeout, conflict, duplicate, disconnect, unavailable operator |
| — | [`10_CHANNEL_ADAPTERS.md`](10_CHANNEL_ADAPTERS.md) | Channels as provider-independent adapters (Harnesses) |
| — | [`11_GOVERNANCE.md`](11_GOVERNANCE.md) | Carry-never-decide; fail-closed; audit; how Engineering Intelligence uses it |
| — | [`12_EXTENSIBILITY.md`](12_EXTENSIBILITY.md) | Absorbing new channels; the reference autonomous sequence |
| — | [`13_GAPS.md`](13_GAPS.md) | Open questions and deferred decisions |
| — | [`ARCHITECTURE_REVIEW.md`](ARCHITECTURE_REVIEW.md) | Correctness, completeness, readiness, ratification verdict |

## Canon (binding for every document)

- **Human Interaction (HI)** — the subsystem specified here. Carries interactions with humans;
  never decides an approval, evaluates policy, or authorizes.
- **Interaction** — the durable record of one human touchpoint (`02`). The aggregate.
- **Interaction Request** — the outbound ask: prompt, expected **response schema** (`07`), deadline,
  channel preference (`02`).
- **Interaction Session** — a conversation: an ordered, resumable series of exchanges sharing
  context (`04`).
- **Response** — the human's inbound reply, validated against the request's response schema (`07`).
- **Decision** — the settled outcome derived from a response; for an approval it carries the single
  platform **`ApprovalTaxonomy`** value (ADR-004), never a competing one (`05`).
- **Channel Adapter** — the provider-specific driver for one channel (Discord/email/CLI/web/…), a
  Communication-category Harness (`10`, INV-34/36).
- **Dependency direction** — `nexus_human_interaction → { nexus_core, nexus_infra }` only. HI is
  coupled to every other subsystem **only through events** (INV-39): it observes interaction-request
  events (e.g. `runtime.waiting_approval`, `actuation.approval_requested`, clarification/escalation
  requests) and emits correlated response/decision events they consume. It imports no engine and is
  imported by none.
- **Determinism seam** — a human response is a **non-deterministic value captured as a recorded
  event** (INV-17); replay reproduces the governed outcome without re-asking the human — the same
  seam already used for LLM output and the existing approval decision (`../runtime/14` §4).
- **Binding invariants** — INV-13/14 (event-sourced), INV-16 (idempotent, dedup duplicate
  approvals), INV-17 (responses as recorded data), INV-28 (only Policy Engine evaluates policy),
  INV-29 (the approver authorizes), INV-30 (fail-closed — no response is **never** an implicit
  grant), INV-31 (every interaction auditable), INV-34/36 (channels are Harnesses), INV-39
  (event-correlated). ADR-004 (single `ApprovalTaxonomy`) is binding and never duplicated. No
  document may weaken these.
