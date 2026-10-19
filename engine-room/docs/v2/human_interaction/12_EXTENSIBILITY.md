# Extensibility

Status: Target Architecture (design only)

---

# Purpose

This document shows how new channels integrate without redesign, and walks the **reference autonomous
sequence** the exercise posed — proving the subsystem carries a real end-to-end engineering task's
human touchpoints.

---

# New channels absorb without redesign

The set of channels is **open** because the interaction model is **closed**. A new channel — Discord,
Slack, email, CLI, VS Code, web, Teams, mobile, voice, or one not yet imagined — joins by supplying a
**Channel Adapter** (`10`) that:

1. registers a Communication Harness descriptor advertising the response schemas it can carry (INV-36,
   `10` concern A);
2. translates provider mechanics onto the **existing** contract — present, deliver, collect, attribute,
   redact, fail honestly (`10` §contract);
3. emits only the canonical `interaction.*` events (`08`) and normalizes replies to the existing
   response schemas (`07`).

Nothing else changes — not the HI core, not any requesting subsystem, not the approval model, not any
ADR or invariant. Adding a channel is "an adapter plus a Registry registration" (`../runtime/03` §5),
the same absorption property as runtimes and actuators.

| Pressure from a new channel | Absorbed in | Unchanged |
|---|---|---|
| a novel present/deliver mechanism | the adapter's translation (`10` B/C) | the Interaction model (`02`) |
| an exotic reply mechanism (voice, gesture) | normalize to an existing response schema (`07`) | the response schemas' *members* extend; the model doesn't |
| a schema the channel can't render | advertise only supported schemas; HI routes accordingly (`10` A) | routing logic (`00`) |
| a new delivery/view capability (or lack) | report honestly, incl. *unknown* (`06`) | the `interaction.*` events (`08`) |

---

# The reference autonomous sequence

The exercise posed: *"Open Claude Code." "Repository has merge conflicts." "Need approval before git
push." "Need clarification."* Here is the end-to-end sequence, showing which subsystem raises each
touchpoint and how HI carries it — the walkthrough that closes the loop both prior reviews left open
(`../engineering/14` G10, `../actuation/13` G-9).

```
Operator goal: "fix the bug in D:/project_x, validate, commit, report back"

1. INTENT / CLARIFICATION
   Intent Resolution finds the Goal ambiguous (which bug?).            [needs a human]
   → emits a clarification request
   → HI: clarification Interaction → channel (Discord) → operator answers → Response (INV-17)
   → Intent Resolution proceeds with a resolved Goal.

2. STRATEGY (Engineering Intelligence)
   EI classifies the work, sets autonomy = supervised, places gates:   [decides gates]
   "approval before commit and before report-send" (../engineering/08).
   (No human yet — EI just records the gates in its Engineering Strategy.)

3. ACTUATION — "Open Claude Code"
   Orchestration allocates a Runtime Session; Actuation opens a Claude Code Session
   in a Workspace over D:/project_x (../actuation/04).                  [no human]

4. RECOVERY — "Repository has merge conflicts"
   Actuation hits a merge conflict → actuation.failed (class: command). [needs a human]
   Recovery classifies it as needing guidance → emits an escalation request.
   → HI: escalation Interaction → operator ("resolve ours/theirs? abort?") → Response
   → Recovery directs the chosen path; Actuation enacts it (../actuation/10).

5. VALIDATION
   Fix applied; Validation judges the regression suite from evidence (INV-20). [no human]

6. APPROVAL — "Need approval before git push"
   Actuation reaches the gated commit/push (../actuation/07);           [needs a human]
   Orchestration/RM enforce the pause → actuation.approval_requested { approval_ref, taxonomy }.
   → HI: approval Interaction (ADR-004 taxonomy) → operator approves → Decision (grant)
   → Actuation projects the grant and enacts the commit/push (../actuation/07, ../runtime/14 §4).
   (If the operator does not answer in the wait bound → fail-closed: no push. INV-30.)

7. REPORT-BACK — notification
   The workflow completes; a notification Interaction reports the outcome
   to the operator (../06), with a reference to the Operator Experience for detail.
```

Every human touchpoint — clarification (1), escalation (4), approval (6), notification (7) — is one
kind of Interaction (`03`), carried by one subsystem (HI), over one channel abstraction (`10`),
recorded in one event stream (`08`), and fail-closed where it gates (6, `09`). **This sequence is
what makes the reference request completable unattended** except at the gates a human must clear —
exactly the design intent.

---

# Human-as-actuator, and future modalities

- The Harness model already lists "Human Operator" as a runtime (`../11_HARNESS.md`). A human *doing
  work* (not just deciding) is an Actuator (`../actuation/12`); a human *deciding/answering* is an HI
  Interaction. The two are complementary and both governed — no redesign to support either.
- Future modalities (voice, AR, an agentic operator-assistant) are new **channels** or new **response
  schemas** (`07`), not new architecture: a voice line advertises the choice/confirm schemas it can
  carry and joins as an adapter (`10`).

---

# Guarantees that make this safe

- **No provider assumptions in the core** — HI reasons only in kinds/schemas/events; a provider name
  in the core is an architecture violation (mirror of `../runtime/03` §3).
- **Capabilities (schemas), not providers, are matched** — a channel advertising a supported schema is
  usable the moment it registers (INV-36).
- **Events and kinds are fixed** — a new channel maps onto the canonical `interaction.*` events (`08`)
  and interaction kinds (`03`); it coins none.
- **Uniform governance** — a new channel inherits fail-closed (`09`), audit (`11`), and redaction
  (`10` F) for free; it cannot weaken them.

---

# North Star

The set of ways Nexus can reach a human is open because the way it *models* reaching them is closed. A
new channel, a new modality, a whole new device joins by translating onto the same kinds, schemas, and
events — and the reference engineering task runs unattended, stopping only at the human gates, on any
channel a person happens to be on.
