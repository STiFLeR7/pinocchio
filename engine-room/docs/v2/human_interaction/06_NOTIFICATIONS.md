# Notifications

Status: Target Architecture (design only)

---

# Purpose

This document defines notifications — the one-way interaction kinds — and answers the exercise's
question: should Human Interaction know Discord/Slack/email/push/CLI, or adapters?

**Adapters.** HI is channel-agnostic; every provider lives behind a Channel Adapter (`10`). A
notification is just an interaction whose response schema is *none* (or *acknowledgement*).

---

# Notifications are interactions with no (or minimal) reply

A **notification** is an outbound-only interaction: Nexus tells a human something, expecting no
reply. An **acknowledgement** is the minimal-reply variant: it expects only a "seen/ack" (`03`).
Both are ordinary Interactions (`02`) — they flow through the same deliver pipeline (`01`), emit the
same `interaction.*` events (`08`), and are carried by the same Channel Adapters (`10`) as approvals
and clarifications. Notifications are not a separate mechanism; they are a *kind*.

| Kind | Reply expected | Settles when |
|---|---|---|
| **notification** | none | delivered (or best-effort sent) |
| **acknowledgement** | an ack | the human acknowledges (or the wait bound lapses) |

---

# HI does not know providers — adapters do

The core discipline (identical to runtimes and actuators):

- **HI core is channel-agnostic.** It creates a notification Interaction and routes it; it has no
  knowledge of Discord, Slack, SMTP, APNs/FCM, a terminal, or a web socket.
- **Channel Adapters know providers** (`10`). A Discord adapter renders the notification as a Discord
  message; an email adapter as an email; a CLI adapter as a printed prompt; a push adapter as a push
  notification. Each is a Communication-category Harness (`../11_HARNESS.md`, INV-34/36).
- Adding, swapping, or removing a provider changes **no** HI logic — the same absorption property as
  the rest of the platform (`12`).

```
notification Interaction (channel-agnostic)
   │  route by preference/availability (10)
   ▼
Channel Adapter  (Discord | Slack | email | push | CLI | web | …)
   │  provider-specific rendering + delivery
   ▼
Human
```

---

# Delivery, view, and honest "unknown"

Notifications track delivery and view **only as far as the channel can report it** — the same honest
degradation runtimes use for progress (`../runtime/03` §5):

| Fact | Emitted when the channel can report it |
|---|---|
| `interaction.sent` | HI handed the notification to the adapter |
| `interaction.delivered` | the channel confirmed delivery (email accepted, Discord 200, push receipt) |
| `interaction.viewed` | the channel confirmed a read/seen (where supported) |

Where a channel cannot report delivery or view (fire-and-forget email, a one-way webhook), HI records
the honest value — *sent, delivery unknown* — rather than fabricating a confirmation. Consumers reason
over truthful facts, never invented ones.

---

# Notifications vs the Operator Experience

A notification and the Operator Experience are complementary, not overlapping:

- A **notification** is a **push** — HI actively reaches out to a human on a channel.
- The **Operator Experience** is a **pull** — a human observes persisted state read-only
  (`../runtime/operator`).

A notification may *point at* something the operator can then inspect via the Operator Experience
(by reference, INV-27), but HI pushes the alert; the Operator surface serves the detail. HI never
becomes an inspection surface, and the Operator Experience never reaches out.

---

# Delivery failure is a transport failure, not a workflow decision

If a notification cannot be delivered (channel down, address invalid), HI treats it as a **delivery
failure** (`09`): it may retry, fail over to another channel (`10`), or surface
`interaction.failed`. What an undelivered *notification* means for the workflow is usually nothing
(notifications rarely gate work); where a notification is actually an acknowledgement gate, the same
fail-closed and requester-owns-the-meaning rules as approvals apply (`05`, `09`).

---

# North Star

A notification is the simplest interaction — one-way, no answer — and it obeys the same rules as every
other: channel-agnostic in the core, provider-specific only in adapters, honest about what the
channel can confirm, and recorded like everything else.
