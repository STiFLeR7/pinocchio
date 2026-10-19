# Contract — Operator Request / Resolved Intent

Status: Frozen (Phase 0 contract freeze)
Object: Operator Request / resolved Intent
Primary source: `docs/v2/16_INTENT_RESOLUTION.md`
Binding ADRs: ADR-003 (canonical object model), ADR-001 (event-sourced state)

> Logical contract only. No serialization, storage, transport, schema, or code.
> Field lists are logical (name + meaning + required/optional).

---

## 1. Purpose

The Intent object captures the **input side of Intent Resolution**: a raw operator
request expressed in any modality, together with what the platform has *understood*
about it before a Goal is constructed. It exists to make the operator's request a
first-class, addressable, replayable operational fact — the raw utterance, the
detected interpretation, any detected ambiguity, any clarification the platform
needs, and the confidence of the interpretation.

It is the bridge object between natural human communication and the deterministic
`goal.md`. It does **one job**: hold and progressively interpret an operator request
until it is either resolved into a Goal or abandoned. It never plans, builds context,
selects runtimes, or executes (doc 16, *Architectural Boundaries*).

---

## 2. Ownership

- **Produced by / owned by:** the **Intent Resolution** layer (the canonical layer
  name per ADR-003 §3.5; "Executive Intelligence" is a deprecated alias).
- **State transitions owned by:** Intent Resolution exclusively. No downstream layer
  (Context Engineering, Planning, Execution) may mutate an Intent; they only read the
  Goal it produces.
- Intent Resolution is the *only* producer of both this object and of `goal.md`.
- Per the cross-cutting rules, the Intent carries **no** provider/runtime/health state
  (provider independence, ADR-002) and defines **no** independent authoritative state
  store — its current state is a projection of the event log (ADR-001 / INV-13/14).

---

## 3. Lifecycle

State is a **projection of the event log** (ADR-001; INV-14), not a stored
authoritative machine. Every transition below corresponds to exactly one recorded
event (INV-15). The logical states an Intent moves through:

- **Received** — a raw operator request has been admitted; no interpretation yet.
- **Interpreting** — intent detection, ambiguity analysis, scope and constraint
  discovery are underway (doc 16 *Operational Lifecycle*).
- **AwaitingClarification** — ambiguity exceeded acceptable confidence; one or more
  clarification requests have been issued and the platform is waiting on the operator
  (doc 16 *Clarification*; "clarification preferred over incorrect execution").
- **Resolved** — interpretation succeeded; exactly one Goal (`goal.md`) has been
  produced. Terminal (success).
- **Abandoned** — the request was withdrawn, superseded, or could not be resolved
  (e.g., unrecoverable ambiguity with no operator response). Terminal (non-success).

Allowed transitions: Received → Interpreting; Interpreting → AwaitingClarification;
AwaitingClarification → Interpreting (on operator response); Interpreting → Resolved;
any non-terminal → Abandoned. Clarification rounds may repeat
(Interpreting ↔ AwaitingClarification) until resolved or abandoned. Non-deterministic
interpretation outputs (LLM/human/clock) are captured as recorded event data, never
recomputed on replay (INV-17).

---

## 4. Required Fields

- **identity** — stable, unique identifier for this Intent; addressable and
  replayable for the life of the platform.
- **correlation** — correlation / trace lineage tying this Intent to the request
  session and to every object derived from it (the resulting Goal, and onward). Makes
  the request auditable end to end (cross-cutting identity & correlation rule).
- **raw_request** — the operator's request as originally expressed, preserved
  verbatim and modality-agnostic in meaning (the literal content of natural language,
  a structured request, a conversation turn, or a voice transcript).
- **modality** — the channel/form the request arrived in (e.g., natural language,
  structured request, conversation, voice transcript). Recorded so interpretation is
  explainable; per doc 16 *Inputs*, modality must not change operational behavior.
- **detected_intent** — the platform's current interpretation of what outcome the
  operator desires (the candidate objective). May be provisional while Interpreting.
- **confidence** — the estimated confidence of the current interpretation
  (e.g., High / Medium / Low / Unknown per doc 16 *Confidence*). Drives whether
  clarification is required before a Goal is emitted.
- **status** — the projected lifecycle state (§3). Derived, never authoritative.

---

## 5. Optional Fields

- **ambiguity** — detected ambiguities preventing confident resolution (e.g., missing
  workspace/repository, multiple possible goals, conflicting instructions, undefined
  deliverables, incomplete constraints, missing approvals — doc 16 *Ambiguity
  Detection*). Absent when no ambiguity was detected.
- **clarification_requests** — questions issued to the operator to resolve ambiguity,
  with the reason each was asked. Present only when clarification was needed.
- **clarification_responses** — operator answers received against prior clarification
  requests, recorded as data so the resolution is replayable.
- **missing_information** — information the platform identified as absent but required
  to construct a confident Goal (doc 16 *Outputs*: "Missing Information").
- **detected_domain** — provisional operational domain classification (e.g., Software,
  Research, Writing, Operations) before it is finalized on the Goal.
- **priority_estimate** — provisional urgency estimate (e.g., Critical / High /
  Medium / Low / Background) before it is finalized on the Goal.
- **assumptions** — assumptions the platform made during interpretation, recorded for
  explainability; assumptions are only permitted when operational policy allows them
  (doc 16 *Clarification Before Assumption*).
- **interpretation_rationale** — explanation of what was understood, what was assumed,
  what was missing, and why clarification was requested (doc 16 *Explainable*).
- **source** — provenance of the request (which operator, which surface/session).
- **resolved_goal_ref** — reference (by id) to the Goal (`goal.md`) produced once the
  Intent reaches **Resolved**. Present only in the Resolved state.

---

## 6. Invariants

- **INV-08 (boundary).** An Intent never carries a plan, work package, runtime, or
  procedure. It may carry a *detected outcome*, never *how* to achieve it. (Doc 16
  *Goal Oriented*: Intent Resolution "never produces execution plans.")
- **INV-07.** Exactly one canonical schema for this object; no subsystem introduces an
  alternative representation of an operator request or resolved intent.
- **INV-13 / INV-14.** The Intent's current state and any snapshot are derived
  projections of the append-only event log; nothing not in the log is true.
- **INV-15.** Every Intent state transition emits exactly one event.
- **INV-17.** Non-deterministic interpretation values (LLM detection results, operator
  clarification answers, clock) are captured as recorded event data and reproduced on
  replay, never recomputed.
- **INV-39.** Cross-subsystem hand-off (Intent → Goal → Context Engineering) occurs as
  events carrying correlation and trace identity.
- **Resolution productivity.** A **Resolved** Intent produces exactly one Goal; an
  Intent never produces more than one Goal, and a Goal is never produced from an
  unresolved Intent.
- **Ambiguity never silently propagates** (doc 16): if confidence is below the policy
  threshold, the Intent must enter **AwaitingClarification** rather than emit a Goal.
- **Provider independence (ADR-002).** No provider/runtime/health state is embedded.

---

## 7. Relationships

- **Produces →** `goal.md`. The terminal **Resolved** state yields exactly one Goal;
  `resolved_goal_ref` links to it. The Goal is the contract surface consumed
  downstream — no downstream layer reads the Intent directly.
- **Consumed by:** Intent Resolution only (for its own interpretation loop). Its
  *output* (the Goal) is consumed by Context Engineering (`context_package.md`).
- **Correlation lineage:** shares a correlation/trace identity with `goal.md`,
  `context_package.md`, and every downstream object, so the whole operation is
  traceable back to the original operator request.
- **Governance:** Intent Resolution identifies intent only; it does not enforce
  governance (doc 16 *Relationship with Governance*). Governance decisions on the
  resulting Goal are recorded as separate policy events, not on the Intent.

---

## 8. Versioning Rules

- **Additive evolution only.** New optional fields (e.g., richer modality metadata,
  intent-history links, predictive-completion hints — doc 16 *Future Evolution*) may
  be added without breaking existing consumers.
- **Published shape is immutable.** The meaning of an existing field is never changed
  in place; the recorded request and its interpretation must remain replayable forever
  (ADR-001 event upcasting / append-only event schemas).
- **Required fields are stable.** Promoting an optional field to required, or removing
  any field, requires a new object version (and an ADR if it alters resolution
  semantics). Old Intents remain replayable under their original version via upcasting.
- **Determinism preserved.** Any new field that influences interpretation must be
  captured as recorded data so replay remains deterministic (INV-17).
