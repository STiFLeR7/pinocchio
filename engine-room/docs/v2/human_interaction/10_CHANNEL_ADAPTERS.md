# Channel Adapters

Status: Target Architecture (design only)

---

# Purpose

This document defines the **Channel Adapter** — the provider-specific driver for one channel — and
establishes that all provider knowledge (Discord, Slack, email, push, CLI, web, Teams, mobile, voice)
lives here and **nowhere** in the Human Interaction core.

---

# What a Channel Adapter is

A **Channel Adapter** is the thin, provider-specific boundary that makes one channel look identical to
HI's channel-agnostic core. It is the *only* place the words "Discord", "SMTP", "APNs", or "websocket"
may appear — the same discipline as Runtime Adapters (`../runtime/03` §3) and Actuators
(`../actuation/12`).

A Channel Adapter **is a Harness** of category Communication (`../11_HARNESS.md`, INV-34/36): it
integrates an external system (a messaging provider) and exposes a capability (present-interaction,
collect-response) without leaking provider details or performing business logic (INV-35). Its
availability and health live in the Harness Registry (INV-36); HI reads them, never re-owns them.

```
        ┌─────────────────── nexus_human_interaction ───────────────────┐
        │  HI CORE (generic)               CHANNEL ADAPTERS (specific)   │
        │  ─────────────────               ──────────────────────────   │
        │  • Interaction model (02)        • Discord adapter             │
        │  • Session/conversation (04)     • Slack adapter               │
        │  • response schemas (07)         • email adapter               │
        │  • interaction.* events (08)     • CLI adapter                 │
        │  • failure/timeout (09)          • web adapter                 │
        │  knows: kinds, schemas, events   • voice adapter               │
        │         — NOT providers          knows: HOW one provider       │
        │                                  presents & collects           │
        └────────────────────────────────────────────────────────────────┘
```

---

# The Channel Adapter contract (responsibilities, not signatures)

Every adapter, regardless of provider, is responsible for exactly these concerns. This is conceptual
— no method list, by design (mirroring `../runtime/03` §2):

| # | Responsibility | What the adapter does | What it must NOT do |
|---|---|---|---|
| A | **advertise** | register a Communication Harness descriptor: channel identity, supported response schemas (`07`), delivery/view reporting capability | decide which interaction routes to it (HI routes) |
| B | **present** | render an Interaction Request into the provider's format (a Discord message, an email, a CLI prompt, a spoken prompt) | alter the request's meaning or add a decision |
| C | **deliver** | send it; report `sent`/`delivered`/`viewed` where the provider supports it, honest *unknown* otherwise (`06`) | fabricate a delivery/view confirmation |
| D | **collect** | receive the human's reply and **normalize it to the request's response schema** (`07`) | judge whether the answer is "good" (the requester does — `01`) |
| E | **attribute** | attach who answered / an approval token where the provider supplies one (`07`) | validate that the human *may* answer (Governance does — `11`) |
| F | **redact** | mask secret values at the channel edge (`../actuation/11`) | let a secret value enter an event payload |
| G | **fail honestly** | report delivery/connection failures as typed transport errors (`09`) | swallow a failure or retry silently forever |

The adapter is a **driver, never a decision-maker** — it presents and collects; it decides no
approval, evaluates no policy, and judges no answer.

---

# The same contract, many channels

Every named channel maps onto the identical contract. The columns are provider mechanics; the model
is constant.

| Channel | Presents as | Collects via | Delivery/view reporting | Notable |
|---|---|---|---|---|
| **Discord** | a message (buttons/embeds) | reply / button click | delivered yes; viewed limited | the v1 Dex channel becomes an adapter |
| **Slack** | a message with actions | reply / action | delivered yes; viewed limited | — |
| **email** | an email (links/forms) | reply / link callback | delivered maybe; viewed unknown | asynchronous, long bounds (`deferred`, `../runtime/14` §3) |
| **push** | a push notification | tap → app action | receipt yes; viewed sometimes | notifications-heavy (`06`) |
| **CLI** | a printed prompt | typed input | delivered/viewed implicit | synchronous, immediate |
| **web / Operator UI** | an in-app request card | in-app control | delivered + viewed yes | richest schemas (forms, uploads) |
| **Teams** | an adaptive card | card action | delivered yes | — |
| **mobile** | app screen / push | in-app control | delivered + viewed yes | — |
| **voice** | a spoken prompt (TTS) | spoken/keypad reply (ASR) | delivered yes; viewed n/a | constrained schemas (choice/confirm) |

Read by row for one channel; by column to see the *contract* is constant. A channel that cannot
support a rich schema (voice cannot render a large structured form) advertises the schemas it *can*
carry (concern A); HI routes schema-appropriately (`00`).

---

# Routing and failover

- HI **routes** an Interaction to a channel by the request's channel preference, the target human's
  reachable channels, and adapter availability/health (INV-36). HI decides *which channel*; the
  adapter delivers.
- On delivery failure, HI **fails over** to another advertised channel (`09`); because replies
  correlate by reference not channel (`../runtime/14` §5), a request sent on one channel can be
  answered on another.
- Adding, swapping, or retiring a channel is "an adapter plus a Registry registration" — **no change**
  to HI core (`12`).

---

# North Star

Human Interaction speaks one language — kinds, schemas, events — and every channel is a translator.
Discord, email, a terminal, a voice line: each renders the same request and returns the same schema,
and the core never learns a single provider's name.
