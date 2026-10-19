# The Human Interaction Subsystem

Status: Target Architecture (design only)

---

# What Human Interaction is

Human Interaction is the subsystem that carries every interaction between Nexus and a human.

It is the platform's **conduit to a person**: it takes an interaction request from any subsystem,
reaches the appropriate human through a channel, presents the request, collects a structured
response, manages the conversation and its deadlines, and returns the human's answer as a correlated
event.

It is the canonical form of the "surface" the platform already delegates to. The approval model says
"some surface presents this and collects a decision" (`../runtime/14` §4); actuation gates pause and
wait for an approval (`../actuation/07`); Intent Resolution and Engineering Intelligence request
clarification (`../16`, `../engineering/08`); Recovery escalates to a human (`../19`). Each of these
needs a human reached. Human Interaction is the one subsystem that reaches them.

It holds **no operational intelligence and no authority**. It does not know what a good answer is, it
does not decide an approval, it does not evaluate policy. It knows how to *ask* and how to *carry the
answer back* — nothing more.

---

# What Human Interaction is NOT

- **Not Intent Resolution.** Intent Resolution *decides* an ambiguity needs clarifying and *composes*
  the Goal from the answer (`../16`). HI merely *carries* the clarification question and the reply.
- **Not Engineering Intelligence.** EI *decides* a design question or autonomy gate needs an operator
  (`../engineering/08`). HI carries the discussion; it forms no strategy.
- **Not Planning / Orchestration.** Planning *identifies* approval gates; Orchestration *coordinates*
  them and assigns the taxonomy (`nexus_orchestration/approvals.py`). HI carries the gated request to
  a human and the decision back.
- **Not the Policy Engine or Governance.** The Policy Engine *evaluates* whether approval is required
  (INV-28); Governance / the approver *authorizes* (INV-29). HI evaluates nothing and authorizes
  nothing.
- **Not Runtime / Actuation.** RM and Actuation *enforce the pause* at their boundaries
  (`../runtime/14`, `../actuation/07`). HI is the surface the pause waits on.
- **Not Recovery.** Recovery *decides* a failure needs a human and *decides* what a timeout means. HI
  carries the escalation and the reply.
- **Not Operator Experience.** The Operator Experience is a *read-only* observation/inspection surface
  over persisted state (`../runtime/operator`). HI is the *interactive* request/response surface. One
  watches; the other asks.
- **Not a Notification Service.** Notifications are one *kind* of interaction HI carries (`06`); HI is
  broader (approvals, clarifications, reviews, conversations) and, crucially, is channel-agnostic —
  providers live in adapters (`10`), not in HI.

Human Interaction consumes these subsystems' requests and serves them. It replaces none.

---

# Responsibilities

Human Interaction is responsible for:

- **interaction lifecycle** — create, route, deliver, track, remind, time out, cancel, and close
  every interaction (`02`, `08`);
- **conversation management** — group exchanges into resumable Interaction Sessions; run clarification
  loops; preserve history (`04`);
- **channel routing** — select and drive a Channel Adapter to present the request and collect the
  reply, provider-agnostically (`10`);
- **response collection & validation** — accept the human's reply, validate it against the request's
  response schema, and project it as a Response/Decision event (`07`);
- **delivery/timeout/failure handling** — track delivery and view where a channel can report it,
  enforce deadlines, dedupe duplicates, fail over disconnected channels, and surface unanswered
  requests (`09`);
- **audit** — record every interaction step as an immutable, correlated event (`08`, INV-31/39).

Human Interaction **never**:

- decides an approval, or interprets what a "good" answer is (the requester/approver does);
- evaluates governance policy (Policy Engine, INV-28);
- authorizes an action (Governance/the approver, INV-29);
- identifies or coordinates approval gates (Planning / Orchestration);
- decides what a timeout *means for the workflow* (the requesting subsystem does — `09`);
- knows a provider API (Channel Adapters do — `10`);
- observes operational state for inspection (Operator Experience does).

---

# The deliver → collect pipeline

For one interaction, HI runs this pipeline. It is event-sourced and deterministic on replay
(INV-13/14/17): a human response is a non-deterministic value captured once as a recorded event.

```
Interaction requested        a subsystem emits an interaction-request event (00)
   │
   ▼
Create Interaction           durable record; state = projection of interaction.* log (02)
   │
   ▼
Route to Channel             select a Channel Adapter by preference/availability (10)
   │
   ▼
Deliver                      adapter presents the request to the human   → interaction.sent/delivered
   │
   ▼
Await Response  ◄── remind / time out / fail over (09) ──┐
   │                                                     │
   ▼                                                     │
Collect & Validate           reply checked against the response schema (07)
   │  (invalid → re-prompt within the same Session, 04)  │
   ▼                                                     │
Project Response / Decision  emit correlated event the requester consumes (05, 07, 08)
   │
   ▼
Close Interaction            terminal; recorded (INV-17). Replay never re-asks the human.
```

HI never decides the *content* of the reply, and it never fabricates one. If no valid response
arrives within the deadline, it emits a timeout — **never** an implicit answer (`09`, INV-30).

---

# The load-bearing discipline: carry, never decide

Every responsibility is an *act of carrying*. The moment a step would decide the human's answer,
evaluate a policy, or authorize an action, it has left HI:

| If a step would… | it belongs to |
|---|---|
| decide whether an approval is granted | the approver (INV-29) |
| decide whether approval is required | Policy Engine (INV-28) |
| decide what a timed-out approval means for the flow | the requesting subsystem (Recovery/Governance, `09`) |
| interpret whether a clarification answer is "good enough" | the requester (Intent Resolution / EI) |
| choose an approval taxonomy | ADR-004 (single taxonomy) — HI carries it, opaque |

This is the human-facing form of the same discipline the approval callback model imposes on the
Runtime Manager: *"RM pauses; it does not decide … the decision is always the approver's"*
(`../runtime/14` §1). HI presents and collects; it does not decide.

---

# North Star

Human Interaction is the disciplined messenger of Nexus. It reaches the right human on the right
channel, presents exactly what it was asked to present, carries back exactly what the human said, and
records every step — while deciding nothing on the human's behalf.
