# Human Interaction — Overview

Status: Target Architecture (design only)

---

# Purpose

Human Interaction is the platform's **single home for reaching a human**.

When any subsystem needs a person — to approve an action, clarify an ambiguity, confirm a step,
review an artifact, receive a notification, or make a decision — it does not build its own way to do
so. It hands the interaction to Human Interaction, which presents it through a channel, collects a
structured response, manages the conversation and its timeouts, and returns the correlated
decision/response event the requester consumes.

It is the canonical implementation of the "surface" the platform already delegates to: the approval
model (`../runtime/14` §4–5) and the actuation approval gate (`../actuation/07`) both say "some
surface presents this to a human and collects a decision." Human Interaction *is* that surface —
provider-independent, event-driven, and shared by every subsystem.

---

# Placement — a cross-cutting subsystem, not a pipeline stage

The exercise asked whether Human Interaction sits *inside* the pipeline (Intent → HI → Planning) or
*beside* it (every subsystem → HI → Human). The answer is the second, refined:

**Human Interaction is a cross-cutting shared subsystem, coupled to every layer only through
events** — a peer of Governance, Memory, and the Event Gateway in the cross-cutting services of
`../01_ARCHITECTURE.md`, not a stage in the vertical flow.

```
   Intent Resolution ┐
   Engineering Intel. │
   Planning           │   (interaction request event)        (channel adapter)
   Orchestration      ├────────────────────────────►  Human Interaction  ────────►  Human
   Runtime Mgr        │                                      │  ▲                       │
   Execution Actuation│   (response / decision event)        │  │  (response)           │
   Recovery           │  ◄───────────────────────────────────┘  └───────────────────────┘
   Governance        ┘
```

- Any subsystem that needs a human **emits an interaction-request event**; HI observes it (the same
  surface-agnostic pattern as `../runtime/14` §5), routes it to a channel, and — on reply — **emits a
  correlated response/decision event** the requester consumes.
- HI is *not* placed between Intent and Planning, or anywhere in the linear pipeline. It is invoked
  from many layers, at many points, whenever a human is needed.
- Both edges are **event-mediated** (INV-39), so HI imports no engine and no engine imports HI.

---

# Why cross-cutting and event-mediated (not a stage)

- Human touchpoints occur at **many points**, not one: intent clarification (before Planning), a
  design review (Engineering Intelligence), an approval before push (Actuation), an escalation on
  failure (Recovery). A single pipeline slot could not serve them all.
- Event mediation preserves the **surface-agnosticism the platform already relies on**
  (`../runtime/14` §5): the requester emits an event and does not call HI directly; HI is just the
  canonical consumer of that event and producer of the reply event. This is why "everything
  integrates through this subsystem" without any subsystem *depending* on it.

---

# Inputs

HI observes interaction-request events emitted by other subsystems, all **by event** (INV-39):

| Input event (examples) | Emitted by | Interaction kind |
|---|---|---|
| `runtime.waiting_approval` | Runtime Mgr (`../runtime/14`) | approval |
| `actuation.approval_requested` | Execution Actuation (`../actuation/07`) | approval |
| a clarification request | Intent Resolution (`../16`) / Engineering Intelligence | clarification |
| an escalation request | Recovery (`../19`) / Supervision (`../09`) | escalation |
| a review request | Engineering Intelligence / Validation | review |
| a notification | any subsystem | notification |

Each carries the **subject** (what the human is being asked about, by reference — INV-27), the
required **response schema** (`07`), the governing **`ApprovalTaxonomy`** where relevant (ADR-004),
a **deadline/wait bound**, and **correlation** (INV-39). HI receives references, never embedded
content, and never a Goal or policy to evaluate.

---

# Outputs

| Output | Consumer | Notes |
|---|---|---|
| **`interaction.*` events** | Event log → requesters, Operator Experience, audit | the full lifecycle of every touchpoint (`08`) |
| **Response / Decision event** (correlated) | the requesting subsystem | the human's reply, projected onto the request; for approvals, an ADR-004-tagged Decision (`05`, `07`) |
| **Channel delivery** | the human, via a Channel Adapter (`10`) | provider-specific rendering; HI core stays channel-agnostic |

HI does **not** output a policy verdict, an authorization, a plan, an execution result, or a claim
that an approval "should" be granted. It outputs *what the human said*, faithfully projected.

---

# Dependency direction

```
nexus_human_interaction → { nexus_core, nexus_infra }   (only)
        ▲
        │ consumed by (provider-specific, behind the boundary)
        └── Channel Adapters (Discord / Slack / email / CLI / web / voice …)

every subsystem ──emits interaction-request event──►  Event Log  ──►  Human Interaction
Human Interaction ──emits response/decision event──►  Event Log  ──►  requesting subsystem
   (no direct imports either way — pure event coupling, INV-39)
```

- HI imports no engine; no engine imports HI. Coupling is entirely through events, exactly as the
  runtime approval surface is (`../runtime/14` §5).
- Provider knowledge (Discord/SMTP/…) lives **only** in Channel Adapters (`10`), never in the HI
  core — the same adapter discipline as runtimes (`../runtime/03` §3) and actuators
  (`../actuation/12`).
- HI persists and emits only through the Phase-2 substrate (event store, bus, repositories); it
  invents no new persistence and does not modify `nexus_infra`.

---

# Canon glossary

| Term | Meaning |
|---|---|
| **Interaction** | the durable record of one human touchpoint (`02`). |
| **Interaction Request** | the outbound ask (prompt, response schema, deadline, channel pref). |
| **Interaction Session** | a resumable, multi-exchange conversation (`04`). |
| **Response** | the human's validated reply (`07`). |
| **Decision** | the settled outcome; for approvals, an ADR-004 `ApprovalTaxonomy`-tagged verdict (`05`). |
| **Channel Adapter** | provider-specific driver for one channel; a Communication Harness (`10`). |

---

# North Star

Every layer above knows *when* it needs a human and *what the answer means*. Human Interaction is the
one place that knows *how to reach that human* — across any channel, on the record, and without ever
making the human's decision for them.
