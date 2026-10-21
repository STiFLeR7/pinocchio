# Conversations

Status: Target Architecture (design only)

---

# Purpose

This document defines the **Interaction Session** — how multiple exchanges, clarification loops,
timeouts, later resumption, and history are architected — and how Engineering Intelligence uses it
for design discussions and iterative planning.

---

# What an Interaction Session is

An **Interaction Session** is a conversation: an ordered, resumable series of Interactions that share
context. A single approval is one Interaction; a clarification loop, a design review with follow-ups,
or an iterative planning discussion is an Interaction Session of several Interactions and Responses.

Its **state is a projection of the `interaction.*` event log** (INV-13/14). Restoring the projection
from the log reconstructs the whole conversation exactly (INV-14) — so a Session is durable,
auditable, and replayable, and a human response, captured once as data (INV-17), is never re-asked on
replay.

This is the direct analogue of the long-lived, reattachable actuation Session (`../actuation/04`):
one level over, the same shape — a first-class, event-sourced, resumable conversation, distinct from
any single request.

---

# Multiple exchanges and clarification loops

A clarification loop is a Session that iterates until the requester is satisfied:

```
Session opened (requester needs to resolve an ambiguity)
   │
   ▼
Interaction 1: clarification  →  Response 1
   │  requester (e.g. Intent Resolution / EI) evaluates the answer
   │  (HI does NOT judge sufficiency — 01; the requester does)
   ▼
still ambiguous?  ── yes ──►  Interaction 2: clarification  →  Response 2  ──► …
   │ no
   ▼
Session concluded (requester proceeds; HI closes the Session)
```

- HI **runs the loop's mechanics** (deliver each question, collect each answer, preserve order and
  context). It does **not** decide when the loop is done — the *requester* decides that from the
  answers (Intent Resolution's confidence, `../16`; EI's strategy readiness, `../engineering/`).
- Each round is an Interaction with its own Request/Response; the Session is the thread that binds
  them and carries shared context by reference.

---

# Timeouts

Every Interaction carries a **deadline/wait bound** supplied by the requester's Strategy/policy — HI
enforces it, never invents it (`../runtime/14` §7):

- A Session may set an overall wait bound and per-Interaction bounds.
- On expiry, HI emits `interaction.timed_out` (`08`) and **stops waiting** — it never fabricates an
  answer (INV-30, `09`).
- What a timeout *means* is the requester's call: Intent Resolution may abandon the Goal, Recovery may
  escalate or abort (`09`, `../19`), Governance may fail the gated action closed. HI reports the
  timeout; the requester decides the consequence.

`deferred`-taxonomy approvals (`../runtime/14` §3) typically carry a long bound (an out-of-band
decision expected later); the mechanism is identical — HI enforces whatever bound it was given.

---

# Resuming later

Because a Session is event-sourced and durable, it can be **parked and resumed**:

```
Session live  ──► (no reply; long deferral) ──►  Session suspended (still open, awaiting)
      ▲                                                    │
      │  human replies later, on any channel               │  interaction.reminded (optional)
      └───────────────────────  resume  ◄──────────────────┘   (causation → the original ask)
```

- A suspended Session is **not** a leaked wait: it is bounded (a lapsed overall bound closes it,
  `09`), recorded, and resumable from the log.
- Resumption is channel-independent: a request delivered over Discord may be answered later over
  web or CLI — the reply correlates by the interaction/approval reference, not by channel
  (`../runtime/14` §5, `10`).

This is the human-facing counterpart of the actuation reattach window (`../actuation/10`): a
conversation can be held open, then rejoined, without losing context.

---

# History

The `interaction.*` log **is** the history (INV-13). Every question, answer, reminder, timeout, and
close is an immutable, correlated fact (`08`, INV-39). Consequences:

- The full conversation is queryable as one causal stream (INV-39) — who was asked what, when, on
  which channel, and what they said.
- The Operator Experience projects this history read-only into its timeline/explorer
  (`../runtime/operator`) — HI produces the facts; the Operator surface displays them.
- Nothing is reconstructed or inferred; history is the recorded truth.

---

# How Engineering Intelligence uses conversations

Engineering Intelligence's need for **design discussions, architecture reviews, clarifications, and
iterative planning** (the exercise's Q11) is exactly an Interaction Session:

| EI need | HI realization |
|---|---|
| **clarification** before strategizing (low-confidence Goal) | a `clarification` Session; EI proceeds once its confidence threshold is met (`../engineering/02`) |
| **design discussion** | a multi-exchange Session of `feedback`/`question` Interactions; EI incorporates the answers into its Engineering Strategy (`../engineering/04`) |
| **architecture review** | a `review` Interaction on a proposed strategy/plan artifact (by reference); the human's approve-with-comments becomes an input EI consumes |
| **iterative planning** | a Session whose rounds refine the approach; each round is a recorded Interaction |

Crucially, EI **decides** what to ask and **interprets** the answers into a strategy; HI only carries
the exchange. EI's use of HI creates no second learning path (INV-25/26): a human's answer is a
recorded input to *this* decision (INV-17), not a durable Knowledge write — if it *should* become
learning, that flows through Reflection → Knowledge, never through HI.

---

# North Star

A conversation is a durable, resumable thread of asking and answering. Human Interaction keeps the
thread — ordered, timed, replayable, channel-independent — while the requester decides when the
conversation has said enough.
