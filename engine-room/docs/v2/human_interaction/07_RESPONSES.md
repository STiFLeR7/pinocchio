# Responses

Status: Target Architecture (design only)

---

# Purpose

This document defines the canonical **Response model** — how a human's answer is represented,
validated, and recorded — across free text, structured forms, choices, approval decisions,
acknowledgements, and uploads.

---

# A Response satisfies its Request's response schema

Every Interaction Request declares a **response schema** — the shape a valid reply must take (`02`).
A **Response** is an answer validated against that schema. This is what lets HI accept human input on
any channel and hand back a well-typed answer the requester can consume without re-parsing.

```
Interaction Request  (declares response schema)
        │
        ▼
Human replies (on some channel)  ──►  Channel Adapter normalizes to the schema (10)
        │
        ▼
Validate against schema  ── invalid ──►  re-prompt within the Session (04); NOT coerced
        │ valid
        ▼
Response recorded (interaction.responded, INV-17)  ──►  Decision projected to requester (05)
```

---

# The canonical response schemas

The exercise asked: free text? forms? choices? approval tokens? uploads? All are schemas — a closed
set of shapes, extensible in its *members* the way capabilities are:

| Schema | Shape | Used by (kinds, `03`) |
|---|---|---|
| **none** | no reply | notification |
| **acknowledgement** | a single "seen/ack" signal | acknowledgement, some notifications |
| **free-text** | unstructured text | clarification, feedback, escalation |
| **choice** | one (or many) of an enumerated set | confirmation, clarification, escalation |
| **structured-form** | typed fields (a small schema) | clarification, feedback |
| **approval-decision** | grant / reject (+ optional reason), tagged with the single `ApprovalTaxonomy` (ADR-004) | approval, review |
| **upload-reference** | an attached artifact, carried **by reference** (INV-27) | review, clarification (e.g. a signed file) |

The **approval-decision** schema does not invent a verdict type — it carries the platform's existing
grant/reject + `ApprovalTaxonomy` (`05`, ADR-004). The **upload-reference** schema references the
artifact by id and never embeds its bytes (INV-27); redaction applies at the edge if a channel could
leak a secret (`../actuation/11`).

---

# Validation, not coercion

A reply that does not satisfy the schema is **rejected and re-prompted** within the same Session
(`04`) — never silently coerced into something the human did not intend:

- a free-text answer where a `choice` was required → re-prompt with the choices;
- an ambiguous approval reply ("maybe") where grant/reject was required → re-prompt;
- a malformed structured form → re-prompt the invalid fields.

This protects the requester: a Response event always conforms to the declared schema, so Intent
Resolution, EI, Actuation, etc. can consume it deterministically. HI validates *shape*; it never
judges *content quality* — whether the answer is *good enough* is the requester's call (`01`).

---

# Responses are recorded as data (the determinism seam)

A human response is a **non-deterministic value captured once as a recorded event** (INV-17):

- `interaction.responded` carries the validated Response as data (`08`).
- On **replay**, the recorded Response is reused — the human is **never re-asked** — so the governed
  outcome is reproduced deterministically, exactly as recorded LLM output and the existing approval
  decision are (`../runtime/14` §4, INV-17).
- Idempotent consumption (INV-16) means a duplicate submission of the same Response (a double-click, a
  channel retry) causes no duplicate state change — the basis for deduping duplicate approvals (`09`).

This is the same determinism seam Engineering Intelligence uses for its heuristic generation
(`../engineering/12`): non-deterministic input, recorded once, replayed as data.

---

# Approval tokens and attribution

Where a channel/authority provides one, a Response may carry an **approval token** — a
correlated/signed handle binding *who* authorized *what*:

- it is recorded with the Response (audit, `11`, INV-31) and linked by causation to the originating
  request (INV-39), so "who authorized what" is reconstructable (`../runtime/14` §4);
- it never carries a secret value (redacted/reference-only, `../actuation/11`);
- HI records and forwards it; it does not *validate authority* (that a given human *may* approve is
  Governance's / the Policy Engine's concern, not HI's — `11`, INV-28/29).

---

# What a Response is not

- Not a policy verdict (the Policy Engine's, INV-28).
- Not an authorization judgement of *who may* answer (Governance's, INV-29 — HI records who *did*).
- Not durable Knowledge (an event, not a learned fact — INV-25; learning flows through
  Reflection → Knowledge, not HI).
- Not coerced — an invalid reply is re-prompted, never reshaped.

---

# North Star

A Response is a human's answer, made well-typed and permanent: validated against exactly what was
asked, recorded once as data so replay never re-asks, attributed to who said it, and handed to the
requester as a clean value it can act on.
