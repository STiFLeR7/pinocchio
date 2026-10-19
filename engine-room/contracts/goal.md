# Contract — Goal

Status: Frozen (Phase 0 contract freeze)
Object: Goal
Primary source: `docs/v2/02_OBJECT_MODEL.md`, `docs/v2/16_INTENT_RESOLUTION.md`
Binding ADRs: ADR-003 §3.1 (Goal definition), ADR-001 (event-sourced state)

> Logical contract only. No serialization, storage, transport, schema, or code.
> Field lists are logical (name + meaning + required/optional).

---

## 1. Purpose

A Goal is the **normalized desired operational outcome** plus its metadata — the
universal input to the rest of the Nexus pipeline. It exists to give every downstream
layer (Context Engineering, Planning, Orchestration, Execution, Validation) a single,
stable, domain-agnostic statement of *what success looks like*, decoupled from how the
operator phrased it and from how the work will be done.

Per ADR-003 §3.1, a Goal is a normalized desired outcome **plus metadata, never a
procedure**. It describes outcomes, never implementation (doc 02 *Goal*). It is the
output of Intent Resolution and the first object in the operational hierarchy
(doc 02 *Operational Hierarchy*).

---

## 2. Ownership

- **Produced by / owned by:** the **Intent Resolution** layer (canonical layer name
  per ADR-003 §3.5; the doc 02 ownership table label "Executive Intelligence" is a
  deprecated alias, corrected by ADR-003 §6 to read "Goal | Intent Resolution").
- **State transitions owned by:** Intent Resolution produces and normalizes the Goal.
  The Goal's *operational progress* state is a projection driven by events emitted as
  the pipeline acts on it; no downstream layer redefines or re-owns the Goal object,
  and none may rewrite the operator's intent (doc 16 *Relationship with Planning*:
  "Planning should never reinterpret operator intent").
- Carries **no** provider/runtime/health state (ADR-002). Defines no independent
  authoritative state store (ADR-001).

---

## 3. Lifecycle

State is a **projection of the event log** (ADR-001; INV-14), not a stored
authoritative machine. Each transition emits exactly one event (INV-15). Logical
states of a Goal:

- **Normalized** — the Goal has been constructed and normalized by Intent Resolution
  and is ready for Context Engineering. (Different requests may normalize to the same
  Goal — doc 16 *Goal Normalization*.)
- **Contextualizing** — Context Engineering is building the single Context Package for
  this Goal.
- **Planning** — a Plan is being derived from the Goal + its Context Package.
- **Executing** — work derived from the Goal is in flight.
- **Achieved** — the desired outcome has been reached, determined from Evidence
  (never from runtime self-report; INV-20). Terminal (success).
- **Abandoned** — the Goal was cancelled, superseded, or governance-denied. Terminal
  (non-success).

Allowed transitions: Normalized → Contextualizing → Planning → Executing → Achieved;
any non-terminal → Abandoned. The Goal itself is immutable in its outcome statement
once Normalized; lifecycle reflects the operation's progress *toward* the outcome, not
edits to the desired outcome (see §6). Non-deterministic values are captured as event
data (INV-17).

---

## 4. Required Fields

(Per ADR-003 §3.1: identity, outcome, domain, priority, confidence, constraints,
scope.)

- **identity** — stable, unique identifier; addressable, correlatable, and replayable.
- **outcome** — the declarative, normalized statement of the **desired outcome**
  (what "done" means), expressed as a result, never as steps or a procedure
  (e.g., "Resolve Authentication Failure", not "edit file X then run Y"). This is the
  heart of the Goal and the locus of INV-08.
- **domain** — the operational domain classification (e.g., Software, Research,
  Writing, Operations, Personal, Business). Domain-agnostic process, domain-specific
  label (doc 16 *Domain Agnostic*). Part of Goal Metadata, held *inside* the Goal.
- **priority** — operational urgency (e.g., Critical / High / Medium / Low /
  Background — doc 16 *Priority*). Goal Metadata, inside the Goal.
- **confidence** — Intent Resolution's confidence in this Goal's correctness
  (e.g., High / Medium / Low / Unknown). Goal Metadata, inside the Goal.
- **constraints** — known operational boundaries the outcome must respect (e.g., time,
  budget, governance, deadlines, resource limits — doc 16 *Constraints*). These are
  declared boundaries, not execution steps; constraints always override execution
  preferences (doc 02 *Constraint*).
- **scope** — what work is **included** and what is **explicitly excluded**
  (doc 16 *Scope*). A required structure with two logical parts (included / excluded)
  so downstream layers cannot silently widen the Goal.

---

## 5. Optional Fields

(Per ADR-003 §3.1 optional set: clarifications, source, correlation; plus metadata
permitted to grow per §10.)

- **correlation** — correlation / trace lineage linking the Goal to its originating
  Intent (`intent.md`) and to every derived object. (Treated as optional per
  ADR-003 §3.1, though the cross-cutting identity rule expects every operational
  object to participate in correlation lineage.)
- **clarifications** — the clarifications exchanged during resolution that shaped this
  Goal (questions asked and operator answers), retained for explainability.
- **source** — provenance of the Goal: which operator and which originating Intent /
  request surface produced it.
- **assumptions** — assumptions made during normalization (only where policy permitted
  assumption over clarification — doc 16). Recorded for auditability.
- **rationale** — explanation of what was understood and why the outcome was framed as
  it is (doc 16 *Explainable*).
- **success_definition** — an elaboration of `outcome` describing observable success
  signals at the outcome level (feeds, but does not replace, Validation's
  evidence-based completion). Still an outcome statement, never a procedure.
- **status** — the projected lifecycle state (§3). Derived, never authoritative.

> Goal Metadata (domain, priority, confidence, clarifications) lives **inside** the
> Goal object, not as separate top-level objects (ADR-003 §3.1).

---

## 6. Invariants

- **INV-08 (primary).** A Goal describes an outcome and **carries no plan, no work
  package, no runtime, no procedure, no step**. Any procedural content is a contract
  violation. (ADR-003 §3.1; doc 02 *Goal*; enforced by contract + negative tests.)
- **INV-07.** Exactly one canonical Goal schema; no subsystem introduces an alternate
  representation. Goal Metadata is not split into separate objects (ADR-003 §3.1).
- **One Context Package per Goal.** Every Goal produces exactly one Context Package
  (doc 02 *Context Package*; see `context_package.md`).
- **Scope is closed.** The included/excluded scope is authoritative; downstream layers
  may not expand the Goal beyond its declared scope.
- **Outcome immutability.** Once Normalized, the desired `outcome` and `scope` are not
  edited by downstream layers; Planning never reinterprets intent (doc 16). Changing
  the desired outcome means a new Goal, not an in-place rewrite. (Consistent with
  INV-22: Recovery never changes the Goal.)
- **INV-13 / INV-14 / INV-15.** State is a projection of the authoritative event log;
  every transition emits exactly one event.
- **INV-20 (completion).** A Goal reaches **Achieved** only on the basis of Evidence
  produced by Validation, never on runtime self-report.
- **Provider independence (ADR-002).** No provider/runtime/health state embedded.
- **Governance.** The Goal does not enforce governance; constraints may encode
  governance boundaries, and governance decisions are recorded as policy events
  (doc 16 *Relationship with Governance*; ADR-003 §9 maps v1 governance flags to Goal
  constraints + policy events).

---

## 7. Relationships

- **Produced by →** `intent.md` (the resolved Intent yields exactly one Goal).
- **Produces →** exactly one `context_package.md` (Context Engineering builds one
  Context Package per Goal).
- **Feeds →** `plan.md`. Planning transforms the Goal (+ its Context Package) into a
  Plan; the Goal is referenced by, never embedded as procedure in, the Plan.
- **Referenced by →** `work_package.md` (a Work Package records its parent Goal id per
  ADR-003 §3.2 Identity) and, transitively, by execution/validation objects via
  correlation lineage.
- **Constraints** within the Goal relate to the broader `policy.md` / Constraint
  vocabulary but are declared boundaries on this Goal, not policy definitions.

---

## 8. Versioning Rules

- **Additive evolution only.** Goal Metadata may grow (e.g., urgency models,
  multi-operator goals — ADR-003 §10) by adding optional fields within the Goal's
  optional-field + versioning rules; no new sibling metadata objects are introduced.
- **Published shape is immutable.** Existing fields are never re-meaninged in place;
  Goals remain replayable forever via event upcasting (ADR-001).
- **Required set is stable.** The required set (identity, outcome, domain, priority,
  confidence, constraints, scope) is fixed by ADR-003 §3.1; changing it requires a new
  object version and a superseding ADR. Old Goals remain replayable under their
  original version.
- **No procedural drift.** No future field may introduce plan/procedure/runtime
  content into the Goal; such growth must live in `plan.md` /
  `execution_strategy.md` / `work_package.md`, preserving INV-08.
