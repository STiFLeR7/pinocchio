# Interaction Types

Status: Target Architecture (design only)

---

# Purpose

This document defines the canonical, **closed** set of interaction kinds, distinguishes kinds from
outcomes, and argues the set is complete.

---

# The canonical kinds

Every human touchpoint is one of these eight kinds. The set is closed: a new situation maps onto an
existing kind; it does not coin a ninth (mirroring the closed event/state discipline of
`../runtime/03` §5).

| Kind | Direction | Gate? | Response schema (`07`) | Example |
|---|---|---|---|---|
| **notification** | outbound only | no | none | "Briefing generated." |
| **acknowledgement** | request → ack | no | acknowledgement | "Deployment starting — please ack." |
| **clarification** | request → info | no | free-text / choice / form | "Which repository did the bug appear in?" |
| **confirmation** | request → yes/no | soft gate | choice (proceed/cancel) | "Proceed to run the full test suite?" |
| **approval** | request → decision | **hard gate** | approval-decision (ADR-004) | "Approve commit to `main`?" |
| **review** | request → judgement | soft/hard gate | approve-with-comments / request-changes | "Review this proposed migration." |
| **feedback** | request → open input | no | free-text / form | "How should this API read?" |
| **escalation** | request → decision/guidance | situational | free-text / choice / decision | "Merge conflict I can't resolve — how do you want to proceed?" |

---

# Kinds vs outcomes (the exercise's list, disentangled)

The exercise listed *rejection* and *decision* alongside the kinds. These are **outcomes**, not
kinds — they are what a Response/Decision *contains*, not what is *asked*:

| Exercise term | Actually a… | Where it lives |
|---|---|---|
| clarification | kind | `03` |
| approval | kind | `03` |
| **rejection** | **outcome** of an approval/review | a Decision value (`05`) |
| confirmation | kind | `03` |
| notification | kind | `03` |
| escalation | kind | `03` |
| review | kind | `03` |
| feedback | kind | `03` |
| acknowledgement | kind | `03` |
| **question** | ≈ **clarification** | merged into clarification |
| **decision** | **outcome** (the settled result) | a Decision (`05`) |

Modeling rejection and decision as *kinds* would be a category error: you do not *ask a rejection*;
you ask an approval and the human *may reject*. Keeping kinds (what is asked) separate from outcomes
(what is answered) keeps the model clean and the response schemas coherent (`07`).

---

# Are these complete? — the completeness argument

Completeness is not asserted; it is argued from two orthogonal axes that partition every possible
human touchpoint:

**Axis 1 — direction:** does the interaction expect a reply?
- *outbound-only* (no reply expected)
- *request-response* (a reply is expected)

**Axis 2 — the nature of the reply the requester needs:**
- *nothing* (fire-and-forget)
- *acknowledgement* (proof of receipt)
- *information* (data to proceed)
- *a decision* (a gated choice that authorizes/blocks)
- *open judgement* (qualitative input)

Every kind occupies a cell; every cell is covered:

| | nothing | acknowledgement | information | a decision | open judgement |
|---|---|---|---|---|---|
| **outbound-only** | notification | — | — | — | — |
| **request-response** | — | acknowledgement | clarification | confirmation / approval / escalation | review / feedback |

Any conceivable touchpoint reduces to "does it want a reply, and of what nature?" — and lands in one
of these cells. A hypothetical new need (say, "solicit a signed artifact") is not a new kind; it is
an existing kind (clarification/approval) with a new **response schema** (`07`, upload/signature).
The kinds are complete; the *response schemas* are the open, extensible dimension.

---

# Why gate-ness is a property, not a kind

Note that *approval*, *confirmation*, *review*, and *escalation* can all *gate* work, while
*notification*, *acknowledgement*, *clarification*, and *feedback* do not. But HI does not own
gating — Planning identifies gates, Policy/Governance decide them, RM/Actuation enforce them (`05`).
So "gate?" in the table above describes how the *requester* uses the interaction, not a behavior HI
implements. HI treats an approval and a clarification identically in mechanics (deliver, collect,
project); only the requester's downstream handling differs.

---

# North Star

Eight kinds, defined by whether a reply is expected and of what nature, cover every way Nexus needs a
human. What is asked (the kind) stays separate from what is answered (the outcome), and new needs
extend the response schema — never the kind list.
