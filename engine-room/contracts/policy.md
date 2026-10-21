# Contract — Policy

Status: Frozen (Phase 0 contract freeze)
Object: Policy
Primary source: `docs/v2/20_POLICY_ENGINE.md`, `docs/v2/12_GOVERNANCE.md`
Binding ADRs: ADR-004 (policy engine & governance), ADR-001 (event-sourced state)

> Logical contract only. No serialization, storage, transport, schema, or code.
> Field lists are logical (name + meaning + required/optional).

---

## 1. Purpose

A Policy is a **versioned, data-driven declarative rule** that defines an operational
boundary within which planning, orchestration, execution, validation, recovery, and
governance must operate. It exists so that operational decisions are made
**consistently, deterministically, explainably, and auditably** from a single
centralized definition rather than from rules hardcoded across subsystems (doc 20
*Why Policy Engine Exists*; INV-28).

A Policy does **one job**: it expresses, as data, *under which operational conditions*
a governed action receives *which decision* (and *which constraints* apply). It is a
**structured condition tree over typed operational attributes — never an embedded DSL
or any general-purpose/Turing-complete language** (ADR-004 §3.1). A Policy never
performs behavior, never executes work, never plans, never creates goals, and never
overrides governance (doc 20 *Architectural Boundaries*). It is *evaluated* by the
Policy Engine; it does not evaluate itself.

Critically, a Policy expresses **governance decisions only**. Recovery strategies
(Retry / Rollback / Abort) are **not** policy decisions (ADR-004 §3.2); Recovery owns
strategy selection and may *consult* policy (receiving Allow/Deny) but never receives a
recovery strategy *as* a Policy Decision.

---

## 2. Ownership

- **Produced by / owned by:** the **Governance** domain owns governance policies and the
  policy set as authority; subsystems (Execution Strategy, Validation, Planning,
  Recovery) declare the policies in their domains. Authorship of a policy belongs to its
  declared **Owner** field.
- **Evaluated by:** the **Policy Engine** exclusively (INV-28). No subsystem hardcodes
  governance rules or evaluates policies directly; subsystems *query* the Policy Engine
  ("Is this allowed?") and receive a Policy Decision (doc 20 *Relationship with
  Planning/Validation/Recovery*; doc 12 *Policy Driven*).
- **Authorization vs. evaluation:** Governance **authorizes** (runs the approval
  workflow, writes immutable audit) but **never executes, plans, supervises, or
  validates** (INV-29). The Policy Engine produces decisions; it performs no action and
  never performs governance (doc 20 *Architectural Boundaries*; ADR-004 §3.2).
- **State transitions owned by:** the Policy registry / Governance ownership boundary;
  lifecycle transitions are recorded as events (ADR-001). A Policy carries **no**
  provider/runtime/health state (provider independence, ADR-002) and defines **no**
  independent authoritative state store — its current state and version history are
  projections of the event log (INV-13/14).

---

## 3. Lifecycle

State is a **projection of the event log** (ADR-001; INV-14). Every transition below
corresponds to exactly one recorded event (INV-15). Lifecycle of a Policy (doc 20
*Policy Lifecycle*):

- **Registered** — the policy has been admitted to the registry with an identity and
  version; not yet usable.
- **Validated** — the policy's condition tree, decision, and constraints have been
  checked as well-formed (predicates reference known attributes; decision is in the
  decision set; specificity is computable).
- **Enabled** — the policy is active and eligible for evaluation against requests.
- **Disabled** — the policy is withdrawn from evaluation (e.g., superseded by a new
  version) but remains addressable for historical replay. Terminal for an active policy.

Per-evaluation flow (not a lifecycle state of the Policy itself, but the runtime path
the Policy participates in — doc 20 *Policy Evaluation*): Request → Applicable Policies →
Condition Evaluation → Conflict Resolution → Decision → Audit. The Decision and Audit are
recorded as events on the *request's* lineage, not as mutations of the Policy. A new
Policy **Version** is a new entry (additive), never an in-place mutation of an Enabled
policy (§8; ADR-001 append-only). Historical executions always reference the exact policy
version that was evaluated (doc 20 *Policy Versioning*).

---

## 4. Required Fields

- **identity** — stable, unique identifier for this Policy, distinct from its version;
  addressable and replayable for the life of the platform.
- **version** — the version of this Policy. Together with `identity` it uniquely
  identifies the exact rule that was evaluated; historical executions reference
  `identity` + `version` so evaluation is replayable (doc 20 *Versioned*, *Policy
  Versioning*).
- **purpose** — the operational intent of the policy: what boundary it enforces and why
  (supports explainability — doc 20 *Explainable*).
- **conditions** — the **structured condition tree** that determines applicability and
  match: a boolean combination (`all` / `any` / `not`) of **typed predicates** over
  **named operational attributes** (e.g., `risk_level`, `domain`, `workspace`,
  `cost_estimate`, `actor`). Each predicate binds one attribute via a typed comparison
  (e.g., equals, one-of, threshold). This is **data, not code** (ADR-004 §3.1). The count
  of **bound attribute predicates** is the policy's *specificity* (§6, conflict
  resolution). An empty/always-true condition tree marks a catch-all (e.g., the Default
  Policy).
- **decision** — the governance outcome this policy yields when its conditions match,
  drawn from the fixed **decision set**: `Allow`, `Deny`, `RequireApproval`, `Delay`,
  `Escalate`, `RequestInformation` (ADR-004 §3.2). Recovery strategies
  (Retry/Rollback/Abort) are **never** valid values here (ADR-004 §3.2).
- **priority** — the deterministic tiebreaker applied *after* specificity when two
  applicable policies are equally specific (§6; doc 20 *Conflict Resolution*).
- **owner** — the authority/domain accountable for this policy (e.g., Governance,
  Execution Strategy, Validation, Planning, Recovery domain). Used for audit and change
  authority (doc 20 *Policy Registry*; doc 12 *Human Authority*).
- **status** — the projected lifecycle state (§3). Derived, never authoritative.

---

## 5. Optional Fields

- **constraints** — bounded operational limits the policy asserts when it applies (e.g.,
  maximum runtime, retry limits, allowed runtimes, concurrency limits, cost limits,
  required evidence, minimum coverage — doc 20 *Policy Categories*). Constraints qualify
  the decision; they are declarative and never executed by the policy.
- **approval_requirement** — when `decision` is `RequireApproval`, the required approval
  **level** from the single platform taxonomy (ADR-004 §3.3): `Automatic` (no human;
  policy authorizes), `HumanReview` (one human approver), `MultiStage` (multiple/
  sequential approvers or gates), `Deferred` (approval obtained at a later defined
  checkpoint). Execution Strategy declares the level; Governance evaluates and enforces
  it (ADR-004 §3.3). No divergent approval vocabulary is permitted.
- **category** — the policy's domain classification (Governance / Execution / Planning /
  Validation / Recovery — doc 20 *Policy Categories*). Note: a *Recovery* policy declares
  *constraints/permissions* Recovery may consult (e.g., "is a runtime switch
  permitted?"); it still yields only a governance `decision`, never a recovery strategy
  (ADR-004 §3.2).
- **governed_action_class** — the class of action this policy governs; absent or marked
  *ungoverned* for explicitly ungoverned action classes (which are allow-by-default —
  ADR-004 §3.1).
- **exceptions** — declared carve-outs to the policy (doc 12 *Policy Model*), expressed
  as data within the condition tree's semantics, recorded for explainability.
- **dependencies** — references to other policies this policy composes with when complex
  decisions require multiple policies (doc 20 *Policy Composition*, *Policy Registry*).
- **audit_requirements** — what an evaluation of this policy must record beyond the
  platform default (doc 12 *Policy Model*; doc 20 *Policy Auditing*).
- **rationale** — author-supplied explanation of the rule's reasoning, recorded for
  explainability and change review.
- **metadata** — non-behavioral descriptive attributes (tags, ownership notes,
  provenance) that do not affect evaluation.
- **effective_window** — an optional validity window (logical, not provider state)
  during which the policy is eligible; outside it, the policy is treated as
  non-applicable.

---

## 6. Invariants

- **INV-28.** Policies are evaluated **only** by the Policy Engine; no subsystem
  hardcodes governance rules. Evaluation is centralized, data-driven, and deterministic
  (ADR-004 §3.1).
- **INV-29.** The Policy/Governance boundary holds: Governance authorizes (approval
  workflow + immutable audit) but never executes, plans, supervises, or validates; the
  Policy Engine decides but performs no action.
- **INV-30 — Fail closed.** When **no** policy matches a **governed** action, the
  **Default Policy** denies (deny-by-default). Allow-by-default applies **only** to
  explicitly ungoverned action classes (ADR-004 §3.1; honors v1 A-001).
- **Decision set is closed.** `decision` is one of exactly
  {`Allow`, `Deny`, `RequireApproval`, `Delay`, `Escalate`, `RequestInformation`}.
  Recovery strategies (Retry/Rollback/Abort) are **never** Policy Decisions (ADR-004
  §3.2).
- **Deterministic conflict resolution.** When multiple policies apply, the winner is
  selected by the fixed order **Specificity → Priority → Version → Default Policy**
  (ADR-004 §3.1; doc 20 *Conflict Resolution*). **Specificity** is defined as the number
  of bound attribute predicates the policy matches (more constrained = more specific).
  Resolution is total and deterministic: identical request + identical applicable policy
  set always yields the identical winner and decision (doc 20 *Deterministic*).
- **No embedded DSL.** `conditions` is a structured data tree of typed predicates over
  named attributes — never a script, expression language, or Turing-complete construct
  (ADR-004 §3.1, §4).
- **Single approval taxonomy.** Any approval level uses only
  {`Automatic`, `HumanReview`, `MultiStage`, `Deferred`} (ADR-004 §3.3). Governance's
  historical "Explicit Approval" maps to `HumanReview` or `MultiStage` by risk.
- **INV-07.** Exactly one canonical schema for Policy; no subsystem introduces an
  alternative policy representation.
- **INV-13 / INV-14.** A Policy's current state and version history are derived
  projections of the append-only event log; nothing not in the log is true.
- **INV-15.** Every Policy lifecycle transition emits exactly one event.
- **INV-17 (replay without re-inference).** A recorded evaluation references the exact
  `identity` + `version` and the captured decision; replay reproduces the governed
  outcome from recorded data and **never re-evaluates** against a changed policy set
  (ADR-004 §3.5; doc 20 *Policy Versioning*).
- **INV-31.** Every policy evaluation is explainable and auditable: it records matched
  policy, evaluated conditions, decision, and reasoning as log data (doc 20
  *Explainable*, *Observable*).
- **Side-effect-free simulation.** The condition tree's data-driven nature allows
  simulation ("what would happen if this policy changed?") that never affects production
  execution (doc 20 *Policy Simulation*; ADR-004 §6).
- **Provider independence (ADR-002).** No provider/runtime/health state is embedded.

---

## 7. Relationships

- **Evaluated by →** the Policy Engine, which produces a **Policy Decision** consumed by
  Governance (authorization), Planning (queries — never evaluates), Execution Strategy
  (approval level), Validation (declares validation policy; Validation layer still owns
  the verdict — ADR-004 §3.4), and Recovery (consults Allow/Deny; Recovery still owns
  strategy — ADR-004 §3.2).
- **Constrains →** `work_package.md`, `execution_strategy.md`, and other governed
  objects through decisions and constraints; it never mutates them.
- **Approval taxonomy shared with** `execution_strategy.md`: Execution Strategy declares
  the required approval level; this Policy's `approval_requirement` uses the identical
  vocabulary (ADR-004 §3.3).
- **Audit →** governance decisions and policy evaluations are recorded as immutable
  events in the authoritative log (ADR-001; doc 12 *Audit*), not in a separate policy
  store that could disagree.
- **Composition:** may reference other Policies via `dependencies` when an operational
  decision requires multiple policies combined (doc 20 *Policy Composition*).
- **Knowledge:** a Policy may be *referenced by* a Knowledge `Constraint` object
  (`knowledge.md`) as understood organizational policy; Knowledge references, never
  duplicates (INV-27).
- **Does not reference** Recovery strategy objects: Recovery strategy selection lives in
  Recovery and is never a Policy field or decision (ADR-004 §3.2).

---

## 8. Versioning Rules

- **Versioning is the unit of change.** A Policy is never mutated in place once Enabled;
  a change produces a new **version** under the same `identity`. The prior version
  remains addressable so historical executions replay against the exact version they
  evaluated (doc 20 *Policy Versioning*; ADR-001 append-only).
- **Additive predicate vocabulary.** New typed predicate kinds and new named attributes
  may be added over time as additive, versioned changes; expressiveness grows without
  introducing a DSL (ADR-004 §5, §7, §10). Existing condition trees remain valid.
- **Decision set and approval taxonomy are fixed** at the architecture level; extending
  either requires an ADR superseding ADR-004, never an ad-hoc policy field.
- **Default Policy is permanent.** The deny-by-default fail-closed Default Policy is a
  platform invariant (INV-30); it may not be weakened to allow-by-default for governed
  actions without superseding ADR-004.
- **Determinism preserved.** Any new attribute or predicate influencing evaluation must
  be captured as recorded data so replay stays deterministic (INV-17; ADR-004 §3.5).
- **Required fields are stable.** Promoting an optional field to required, or removing a
  field, requires a new object version (and an ADR if it alters evaluation, conflict
  resolution, or the decision set). Old policies remain replayable under their original
  version via upcasting.
