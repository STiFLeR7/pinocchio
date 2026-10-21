# Event Model

Status: Target Architecture (design only)

---

# Purpose

This document defines the canonical **`interaction.*`** event taxonomy — the append-only facts that
are the single source of truth for every human touchpoint — and how it correlates with the
originating gate/clarification/escalation events without duplicating them.

---

# Events are the source of truth

Per ADR-001 / INV-13, the append-only log is authoritative; an Interaction's, Session's, and
Response's state is a **projection** of the `interaction.*` log (INV-14), idempotent (INV-16) and
deterministic on replay (INV-17 — the human response lives in the payload as data). Every event
carries correlation and trace identity, and decision/response events carry **causation** back to the
originating request (INV-39, `../runtime/14` §4).

HI events are the human-facing analogue of `runtime.*` and `actuation.*`: HI emits facts; consumers
(requesters, Operator Experience, audit) react to them; none writes back into HI state (one-way,
INV-16).

---

# The canonical taxonomy

The exercise's examples are the spine; the full closed set adds reminders, escalation, and delivery
failure. A new channel or kind maps onto these and coins none of its own (`12`).

## Lifecycle (the exercise's core set)

| Event | Fact |
|---|---|
| `interaction.created` | an Interaction was created from a request event |
| `interaction.sent` | HI handed the Interaction to a Channel Adapter for delivery |
| `interaction.delivered` | the channel confirmed delivery (honest *unknown* where unsupported — `06`) |
| `interaction.viewed` | the channel confirmed the human saw it (where supported) |
| `interaction.responded` | a valid Response was collected (the response is the payload, INV-17) |
| `interaction.timed_out` | the wait bound lapsed with no valid response (fail-closed — `09`, INV-30) |
| `interaction.cancelled` | the requester withdrew the request (e.g. the gated work was aborted) |
| `interaction.closed` | the Interaction reached a terminal state; nothing further |

## Additional (closed set completion)

| Event | Fact |
|---|---|
| `interaction.routed` | a Channel Adapter was selected (records the channel choice, `10`) |
| `interaction.reminded` | a reminder was re-sent before the deadline (`04`, `09`) |
| `interaction.reprompted` | an invalid Response was rejected and re-asked (`07`) |
| `interaction.escalated` | the Interaction was escalated (channel failover or to another authority, `09`) |
| `interaction.failed` | a delivery/transport failure occurred (channel down, invalid address — `09`) |

## Session (conversations, `04`)

| Event | Fact |
|---|---|
| `interaction.session_opened` | a conversation began |
| `interaction.session_suspended` | the conversation is parked, awaiting a later reply |
| `interaction.session_resumed` | the conversation was rejoined (causation → the suspend) |
| `interaction.session_closed` | the conversation concluded |

---

# `interaction.*` vs the events it answers

HI does **not** duplicate the originating events. It **bridges** them: it *consumes* a subsystem's
request event and *emits* a correlated response/decision event that subsystem consumes.

```
runtime.waiting_approval / actuation.approval_requested / (clarification|escalation request)
        │  (the ORIGINATING event — owned by RM / Actuation / Recovery / EI)
        ▼
   [ Human Interaction ]  interaction.created … interaction.responded
        │  (the DECISION/RESPONSE event, causation = the originating event's id — INV-39)
        ▼
runtime.resumed / actuation continues / requester consumes the answer
```

- The **originating** events stay owned by their subsystems (`../runtime/15`, `../actuation/08`); HI
  coins none of them.
- The **`interaction.*`** events are HI's own facts about *reaching the human*; they are a distinct,
  finer-grained layer (the conversation, the reminders, the channel, the view) that the originating
  events never described.
- The **causation chain** ties them together: the decision event HI emits carries causation = the
  originating `waiting_approval`/request event (`../runtime/14` §4), so the full lineage — gate →
  ask → answer → resume — is one causal stream (INV-39).

---

# Event discipline

- **Never embed content.** The subject (gated action, Goal, artifact), and any uploaded response
  artifact, are referenced by id — never embedded (INV-27, ADR-003). Secret values never enter a
  payload (redacted at the channel edge, `../actuation/11`).
- **Human input is data.** `interaction.responded` carries the validated Response as a recorded value
  (INV-17); replay reuses it and never re-asks the human.
- **Correlate and causate.** Every event carries the operation-wide `correlation_identifier`; decision
  events carry causation to the originating request; `session_resumed` to the suspend; `reprompted`
  to the invalid response (INV-39).
- **Deterministic ids.** Event ids derive from stable identities (Interaction id + kind tag +
  monotonic sequence), so the stream is ordered and dedup-keyed (INV-16), and replay yields identical
  state (mirrors `../runtime/02` §3).

---

# What consumers do with the stream

| Consumer | Uses `interaction.*` for |
|---|---|
| **the requesting subsystem** | consume the decision/response event; resume/continue (`05`) |
| **Runtime Mgr / Actuation** | project the approval decision onto the paused session (`../runtime/14` §4) |
| **Operator Experience** | read-only timeline/explorer of interactions and their history (`04`, `../runtime/operator`) |
| **Governance / audit** | the immutable trail of who was asked what, on which channel, and what they said (`11`, INV-31) |
| **Reflection** | interaction patterns as observations feeding Knowledge (indirectly, INV-25/26) |

---

# North Star

If it is not in the `interaction.*` log, no human was asked. Every request, delivery, view, reminder,
answer, timeout, and close is a correlated, immutable, content-free fact — bridged by causation to the
work that raised it and to the resumption it enables.
