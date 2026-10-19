# Skill — Canonical Logical Contract

Status: Frozen (Phase 0 contract freeze)
Object: Skill · Primary source: `docs/v2/06_SKILLS.md` · Binding ADRs: ADR-002, ADR-004

> A logical, implementation-independent specification. Fields are logical
> (name + meaning + required/optional), never wire/typed definitions. No
> serialization, storage, API, or code is implied here.

---

## 1. Purpose

A Skill is a **reusable, runtime-independent operational procedure** — it
captures *how* a type of work should be performed, encapsulating operational
expertise rather than implementation details. A Skill describes the methodology
(phases, checkpoints, expected transitions) without binding to any runtime,
model, tool, or provider.

Skills bridge operator goals and execution engines (`06`): they are the building
blocks Planning composes and Work Packaging packages. The **same Skill runs on
any runtime unchanged** (INV-33). Skills are *procedures*; Capabilities are
*functionality* — distinct objects (ADR-002 §D).

---

## 2. Ownership

- **Produced / owned by:** the **Skill Registry** (ADR-002 — the authoritative
  registry of reusable operational procedures). It owns Skill definitions,
  versions, composition references, and required context. The registry does not
  execute (`06`).
- **State transitions owned by:** the Skill Registry (definitional lifecycle:
  registration, versioning, deprecation). The per-operation *execution* lifecycle
  of a selected Skill is owned by the execution/orchestration layers, projected
  from the Event Log (ADR-001).
- **Consumed by:**
  - **Skill Selection** — determines which Skills satisfy required Capabilities,
    considering capability, context, constraints, and evidence requirements;
    **never considers runtimes** (`06`).
  - **Work Packaging** — packages selected Skills (with resolved context and
    strategy) into Work Packages for Execution.
- **Validation/Recovery declaration vs. evaluation (ADR-004 §3.4):** a Skill
  *declares* default Validation and Recovery strategies, but it **never owns**
  their evaluation. Validation *verdicts* are owned by the **Validation layer**;
  Recovery *strategy selection* is owned by **Recovery**. Declaration ≠ evaluation.

---

## 3. Lifecycle

The Skill **definition** is versioned and append-only in the registry. A
*selected* Skill instance moves through an execution lifecycle whose state is a
projection of the Event Log (ADR-001); every transition emits exactly one Event
(INV-15).

```
Registered → Selected → Prepared → Executing → Validated → Completed
```

**Failure / terminal states:**

```
Blocked · Failed · Cancelled · Expired
```

- **Registered** — published in the Skill Registry, discoverable for selection.
- **Selected** — chosen by Skill Selection to satisfy required Capabilities.
- **Prepared** — Required Context assembled by Context Engineering; packaged.
- **Executing** — performed by an assigned runtime (the Skill itself is runtime-
  independent — INV-33).
- **Validated → Completed** — completion is determined by the Validation layer
  from independent Evidence, never by runtime self-report (INV-20, INV-21).

Definition versions are immutable once published; change means a new version
(ADR-001 additive evolution).

---

## 4. Required Fields

| Field | Meaning |
|-------|---------|
| **Identity** | Stable identifier + human-readable Name; participates in correlation/trace lineage. |
| **Version** | Definition version. Skills version independently as procedures (ADR-002 §D). |
| **Purpose** | The operational capability this Skill provides — what work it knows how to perform. |
| **Inputs** | Required information to perform the procedure (e.g. repository, research question, document, workspace, context package) — logical roles, not wire schemas. |
| **Outputs** | Expected deliverables (e.g. report, implementation, summary, review, documentation) — logical roles. |
| **Procedure** | The operational methodology: **phases, checkpoints, and expected transitions**, described **without binding to any runtime** (INV-33). |

---

## 5. Optional Fields

| Field | Meaning |
|-------|---------|
| **Required Context** | What Context Engineering must provide before execution (e.g. repository, architecture, historical decisions, research sources, existing tasks). Drives context assembly during Prepared. |
| **Constraints** | Operational boundaries inherent to the procedure: approval required, budget, security, workspace restrictions, deadlines, quality requirements (`06`). Declarative; enforcement is Governance/Orchestration. |
| **Validation Strategy (default)** | The procedure's **default** approach to verifying completion (e.g. tests, review, evidence, generated artifacts, independent verification). A **default that Execution Strategy may override** (ADR-004 §3.4). Evaluation is the Validation layer's, not the Skill's. |
| **Recovery Strategy (default)** | The procedure's **default** expected behavior on failure (e.g. retry, escalate, request context, pause, human review). A **default that Execution Strategy may override** (ADR-004 §3.4). Strategy *selection* at runtime is Recovery's. |
| **Category** | Logical grouping (e.g. Analysis, Development, Documentation, Operations, Personal) — taxonomy only. |
| **Composition References** | Other Skills this Skill composes with (`06` Skill Composition). References by Skill Identity/version. |
| **Required Capabilities** | The Capabilities this Skill needs to be satisfiable (references into `capability.md`); one Skill may require multiple Capabilities. |
| **Metadata** | Non-authoritative descriptive attributes (tags, compatibility notes, documentation links). |

---

## 6. Invariants

- **INV-33** — Skills describe operational capability, **never runtime
  implementation**; the same Skill runs on any runtime unchanged. The Procedure
  binds to no runtime, model, tool, or provider. *(Binding for this contract.)*
- **ADR-004 §3.4 (precedence)** — When a Skill and an Execution Strategy both
  carry validation/recovery guidance: **Governance/Policy (hard constraints) →
  Execution Strategy → Skill default**. Skill validation/recovery are
  **overridable defaults**, not authority.
- **Declaration ≠ evaluation** — Validation *verdicts* are owned by the
  Validation layer; Recovery *strategy selection* by Recovery. A Skill only
  *declares* defaults (ADR-004 §3.4; INV-20, INV-21).
- **INV-07** — Exactly one canonical Skill schema; Skills are not redefined as
  Capabilities or Harnesses (ADR-002 §D, alternative D rejected).
- **Selection runtime-blindness** — Skill Selection never considers runtimes
  (`06`); a Skill carries no runtime/provider field.
- **Composition closure** — every Composition Reference and Required Capability
  resolves to an existing Skill / Capability (no dangling references).
- **INV-15 / INV-13** — every execution-lifecycle transition of a selected Skill
  emits exactly one Event; its state is a projection of the authoritative log.

---

## 7. Relationships

- **`capability.md`** — A Skill *requires* one or more Capabilities; one
  Capability may support many Skills (`06`, `21`). Skills are procedures;
  Capabilities are functionality (ADR-002 §D).
- **`execution_strategy.md`** — **authoritative over** the Skill for the
  operation: it may override the Skill's default Validation/Recovery guidance
  (ADR-004 §3.4). The Strategy declares coordination; Orchestration enacts it.
- **`work_package.md`** — Work Packaging packages selected Skills (with resolved
  context + strategy) into Work Packages; Execution receives only Work Packages
  (INV-09, INV-19), never raw Skills or Goals.
- **`policy.md`** — Governance/Policy hard constraints sit **above** Skill
  defaults in the precedence order (ADR-004 §3.4); governed actions fail closed
  (INV-30).
- **`context_package.md`** — a Skill's *Required Context* drives what Context
  Engineering assembles before the Prepared state.
- **Harness Registry / runtimes** — a Skill names no runtime; runtimes are
  selected by Orchestration over resolved capability candidates (INV-37), and the
  same Skill executes on any of them unchanged.

---

## 8. Versioning Rules

- Evolution is **additive**: new optional fields, new Skill versions, or new
  Skills. Published `(Identity, Version)` definitions are immutable.
- A **new Version** is required for any change to Purpose, Inputs/Outputs meaning,
  Procedure phases/checkpoints, or Required Capabilities that alters what a
  consumer (Selection/Work Packaging) expects.
- **Validation/Recovery default** changes are versioned additively; because they
  are *overridable defaults* (ADR-004 §3.4), changing them never alters the
  precedence contract (Governance → Execution Strategy → Skill).
- **Category, Composition References, Metadata** may be extended additively
  without a new object version when no consumer guarantee changes.
- Skills version **independently** of Capabilities, runtimes, and providers
  (ADR-002 §D); runtime support is never recorded on the Skill.
- Old versions remain **selectable and replayable** until deprecated/retired;
  historical references in past Work Packages/events stay valid forever (ADR-001
  event upcasting).
