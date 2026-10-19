# Nexus v2 — Architecture Gaps

Status: Engineering Plan
Scope: The authoritative registry of architectural gaps, contradictions, and
unresolved decisions in `docs/v2/` that must be reconciled before or during
implementation.

---

## How to Read This Registry

A **gap** is a place where the source architecture is internally inconsistent,
under-specified on a load-bearing decision, or defines the same concept in two
incompatible ways. Each gap is assigned an ID (`G#`), a severity, the documents
where it appears, the consequence of leaving it unresolved, the **Action Point**
that owns its resolution (`02_ACTION_POINTS.md`), and a status.

Each gap that requires a recorded architectural decision maps to one or more
ADRs in `09_ADR_BACKLOG.md`. The final section of this document and the closing
table of the ADR backlog are mutually traceable: gap → ADR → blocking AP.

**Severity scale.**
- **Critical** — blocks a foundational decision; wrong resolution forces rework
  of an entire phase.
- **High** — fractures a Phase 1 object schema or a cross-layer contract if not
  reconciled before that phase begins.
- **Medium** — local inconsistency that degrades correctness or auditability but
  does not cascade across layers.
- **Low** — documentation hygiene; no runtime consequence.

**Status.**
- **Open** — unresolved; owned by a Phase-0 (or later) AP.
- **Reconciled** — the structural ambiguity has been removed in `docs/v2/`; only
  schema enforcement remains.

---

## Important: No Missing-Subsystem Gaps Remain

At an earlier absorption pass, three specifications were empty or duplicated
(`09_SUPERVISION` empty, `11_HARNESS` a duplicate of Knowledge, Reflection
absent). They have since been authored. The architecture is now **structurally
complete** (docs 00–26 + README).

Consequently, **none of the gaps below are "missing subsystem" gaps.** Every
remaining gap is a **reconciliation or decision gap**: two documents disagree on
a field set, an enum, an ownership boundary, or a source of truth; or a
foundational decision (persistence model, policy language) is asserted but never
made. Phase 0 is reconciliation work, not authoring work.

---

## Recently Resolved (Now-Populated Specifications)

| Doc | Was | Now |
|-----|-----|-----|
| `09_SUPERVISION.md` | Empty | Populated. Resolves the pause/resume/escalate ownership question: **Supervision recommends** intervention, **Orchestration acts** (`AP-401`), **Recovery decides** the strategy (`AP-503`). |
| `11_HARNESS.md` | Duplicate of Knowledge | Rewritten as a generalized integration-boundary specification (the single contract all external systems implement). |
| `26_REFLECTION.md` | Absent | Populated. Reflection produces advisory Knowledge Candidates only; cleanly separated from Knowledge ingestion and from Planning. |

These three are now treated as **Reconciled** for the subsystems they introduce.
Residual cross-document field/enum/ownership conflicts they participate in are
tracked below as ordinary reconciliation gaps.

---

## Gap Registry

### Critical

#### G1 — Persistence / Event-Sourcing Model Undecided
- **Severity.** Critical.
- **Description.** Three candidate sources of operational truth coexist —
  event-sourced state (state derived from the event log), independently stored
  state, and checkpoints as materialized snapshots. The architecture never
  chooses among event-sourced vs. stored-state vs. hybrid, nor states which
  store is authoritative for "where is this execution now," nor how Checkpoints
  relate to the event log (derived vs. independent). This is the single most
  consequential unmade decision.
- **Where it appears.** Event Model (23), State Model (24), Checkpoint Model
  (25); referenced by Recovery (19) and Execution Graph (18).
- **Impact if unresolved.** All of Phase 2 (Event Bus/Store, State Engine,
  Checkpoint Store) is built on an unspecified consistency model; a wrong or
  late choice forces rework of the entire infrastructure substrate and of
  recovery semantics.
- **Resolution owner.** `AP-001` (→ ADR-001).
- **Status.** Open.

### High

#### G2 — Registry Convergence (Harness · Runtime · Resource · Capability)
- **Severity.** High.
- **Description.** Four registries share near-identical registration fields
  (Identity, Capabilities, Availability, Health, Version, Provider). Provider,
  Availability, and Health live in **both** the Capability registry and the
  Resource registry, creating a dual source of truth. Capability **resolution**
  ownership is unassigned (Capability vs. Resource vs. Orchestration). No
  canonical hierarchy distinguishes abstract capability from allocatable
  instance from integration boundary.
- **Where it appears.** Harness (11), Runtime Model (15), Capability Model (21),
  Resource Model (22).
- **Impact if unresolved.** The Phase 1 Capability/Resource/Harness schemas
  (`AP-108`, `AP-109`) would encode the same field in two registries; runtime
  state (availability/health) would have two writers; capability resolution
  would have no defined owner.
- **Resolution owner.** `AP-002` (→ ADR-002).
- **Status.** Open.

#### G3 — Work Package Defined Three Times with Divergent Field Sets
- **Severity.** High.
- **Description.** Work Package is defined with incompatible field sets in two
  documents. Planning (04) describes objective / inputs / expected outputs /
  dependencies / constraints / required capabilities / validation requirements /
  completion criteria. Work Packages (05) describes Identity / Objective /
  Context (embedded Context Package) / Constraints / Resources / Skills / Inputs
  / Outputs / Evidence / Completion Criteria / Status / Checkpoints /
  Observability. A third, lighter shape is implied by the Planning decomposition
  narrative. These must collapse into one schema — the universal runtime
  contract.
- **Where it appears.** Planning (04), Work Packages (05); consumed by
  Orchestration (07), Execution (08), Validation (14).
- **Impact if unresolved.** Highest contract-drift risk in the platform: every
  layer from Planning through Validation binds to the Work Package; divergent
  definitions guarantee integration failure at the busiest seam.
- **Resolution owner.** `AP-003` (decision) and `AP-105` (unified schema) (→
  ADR-003).
- **Status.** Open.

#### G4 — Execution Graph Containment Contradiction + Redundant Dependency Graph
- **Severity.** High.
- **Description.** The Execution Graph is described as **nested inside** the Plan
  (Object Model, 02) and as a **sibling output** of Planning (Architecture 01,
  Planning 04, Execution Graph 18). Separately, Planning (04) lists a standalone
  "Dependency Graph" output that the Execution Graph (18) absorbs into its
  Execution/Data edges — redundant if the Execution Graph is authoritative.
- **Where it appears.** Object Model (02), Architecture (01), Planning (04),
  Execution Graph (18).
- **Impact if unresolved.** The Phase 1 Plan + Execution Graph schema (`AP-104`)
  and the Phase 3 graph builder (`AP-307`) cannot fix containment or decide
  whether a separate Dependency Graph persists; orchestration's single source of
  topology truth is ambiguous.
- **Resolution owner.** `AP-003` (decision); `AP-104` (schema) (→ ADR-003).
- **Status.** Open.

#### G5 — Observation Dual-Owned (Execution vs. Supervision)
- **Severity.** High.
- **Description.** Execution is said to "produce Observations" (08), while
  Supervision owns the Observation object (02, 09). The reconciled model:
  Execution emits **raw Execution Events**; Supervision **derives and owns**
  Observation. This boundary is implied by the now-populated Supervision spec but
  not yet propagated into the Execution and Object Model documents.
- **Where it appears.** Execution (08), Object Model (02), Supervision (09).
- **Impact if unresolved.** The Observation schema (`AP-110`) and the Execution
  layer (`AP-405`) would have two producers for one object; the
  detection-vs-emission boundary blurs.
- **Resolution owner.** `AP-003` (decision); `AP-110` (schema) (→ ADR-003).
- **Status.** Open.

#### G6 — Intent Resolution == Executive Intelligence (Unpropagated Rename)
- **Severity.** High.
- **Description.** "Intent Resolution" (16) and "Executive Intelligence" (01,
  02) are the same pipeline layer under two names; the rename was never
  propagated. The richer Goal metadata defined in Intent Resolution (confidence,
  domain, priority, clarification state) is not reflected in the Object Model
  (02).
- **Where it appears.** Intent Resolution (16), Architecture (01), Object Model
  (02).
- **Impact if unresolved.** The architecture index and Goal schema (`AP-102`)
  would carry two names and an incomplete metadata set for the universal
  pipeline input.
- **Resolution owner.** `AP-003` (decision); `AP-007` (index/glossary) (→
  ADR-003).
- **Status.** Open.

#### G7 — Goal Object Never Structurally Defined
- **Severity.** High.
- **Description.** The Goal is the universal pipeline input referenced by every
  layer, yet no document defines its structure (outcome fields, metadata,
  constraints, clarification state). Its metadata only appears narratively in
  Intent Resolution (16).
- **Where it appears.** Referenced throughout (01, 02, 03, 04, 16); structurally
  defined nowhere.
- **Impact if unresolved.** Phase 3 (`AP-301` Intent Resolution) has no target
  object to emit and Context Engineering (`AP-303`) has no defined input;
  procedure could leak into the Goal, violating the outcome-not-procedure
  invariant.
- **Resolution owner.** `AP-102` (Goal schema), informed by `AP-003`.
- **Status.** Open.

#### G8 — Approval Taxonomy Mismatch (Governance vs. Execution Strategy)
- **Severity.** High.
- **Description.** Two approval vocabularies coexist. Governance (12) defines
  Automatic / Human Review / Explicit Approval (confirmed at 12_GOVERNANCE.md
  lines 224/234/244). Execution Strategy (13) defines Automatic / Human Approval
  / Multi-stage / Deferred. Governance evaluates the Strategy's approval policy,
  so the two must share one vocabulary.
- **Where it appears.** Governance (12), Execution Model / Strategy (13).
- **Impact if unresolved.** The Execution Strategy schema (`AP-106`), the
  generator (`AP-308`), and the Governance gate (`AP-406`) would speak two
  approval languages across the same seam.
- **Resolution owner.** `AP-004` (→ ADR-004).
- **Status.** Open.

#### G10 — Resource State Contradiction (Two State Machines)
- **Severity.** High.
- **Description.** Resource (22) defines its own availability states (Available /
  Busy / Reserved / Offline / Maintenance / Failed / Unknown). The State Model
  (24) simultaneously lists Resource as a stateful object governed by the
  **generic** lifecycle (Created / Ready / Active / …). Two state machines govern
  one object. Compounding this, the State Model uses "Active" in its lifecycle
  (24, lines 81/235) but cites "Executing" in invalid-transition examples (24,
  lines 459/479) — an internal naming drift.
- **Where it appears.** Resource Model (22), State Model (24).
- **Impact if unresolved.** The Resource/Harness schema (`AP-109`) and the State
  Machine Engine (`AP-203`) cannot decide which state machine governs a Resource;
  illegal-transition guards would be written against an ambiguous vocabulary.
- **Resolution owner.** `AP-002` / `AP-003` (decision); `AP-109`, `AP-203`
  (enforcement) (→ ADR-002, ADR-009).
- **Status.** Open.

#### G13 — Dual Ownership of Recovery + Validation Strategy (No Precedence Rule)
- **Severity.** High.
- **Description.** Skill (06) carries a Recovery Strategy and a Validation
  Strategy. Execution Strategy (13) carries a Recovery Policy and a Validation
  Policy. Validation (14) owns completion determination. No precedence rule
  states which governs when a Skill's strategy and the Execution Strategy's
  policy conflict, nor how either relates to Validation's authority over
  completion.
- **Where it appears.** Skills (06), Execution Model / Strategy (13), Validation
  (14), Recovery (19).
- **Impact if unresolved.** The Skill schema (`AP-107`), Execution Strategy
  schema (`AP-106`), and Recovery Engine (`AP-503`) would each assume ownership;
  recovery and validation behavior become non-deterministic at runtime.
- **Resolution owner.** `AP-003` / `AP-004` (precedence decision); `AP-107`
  (schema) (→ ADR-003, ADR-004).
- **Status.** Open.

#### G14 — Determinism Asserted Over Inherently Non-Deterministic Steps
- **Severity.** High.
- **Description.** The architecture asserts deterministic behavior, but several
  steps are inherently non-deterministic: Intent Resolution (LLM), Execution
  (LLM runtimes — already softened to "attempt identical behavior"), Governance
  approvals (human), Validation Human/Hybrid types, Policy evaluation under
  ambiguous specificity, Recovery strategy selection, and Execution Graph
  conditional edges. The determinism **boundaries** — where determinism is
  guaranteed vs. best-effort — are never stated.
- **Where it appears.** Architecture (01), Intent Resolution (16), Execution
  (08), Governance (12), Validation (14), Policy Engine (20), Recovery (19),
  Execution Graph (18).
- **Impact if unresolved.** Acceptance criteria across Phases 3–5 (`AP-301`,
  `AP-403`, `AP-405`, `AP-502`, `AP-503`) would assert determinism that cannot
  hold; tests would encode false invariants.
- **Resolution owner.** `AP-004` (→ ADR-004).
- **Status.** Open.

### Medium

#### G9 — Validation Enum Drift (Result Set vs. State Set)
- **Severity.** Medium.
- **Description.** Validation's four-valued **result** set is {Passed, Failed,
  Partial, Requires Review} (14_VALIDATION.md lines 120–123), while its
  **state** set includes {Pending, Collecting Evidence, Validating, …, Waiting
  Human Review, Cancelled} (lines 265–275). "Requires Review" (result) and
  "Waiting Human Review" (state) name the same human-in-the-loop condition with
  two terms.
- **Where it appears.** Validation (14).
- **Impact if unresolved.** The Validation Report schema (`AP-112`) and the
  Validation Engine (`AP-502`) would expose two terms for one outcome; the
  Knowledge gate filter becomes ambiguous.
- **Resolution owner.** `AP-112` (schema enum), enforced by `AP-502`.
- **Status.** Open.

#### G11 — Artifact Status vs. Lifecycle Dual Vocabulary + Evidence Field Overlap
- **Severity.** Medium.
- **Description.** The Artifact (17) defines a Lifecycle vocabulary {Created,
  Produced, Validated, Versioned, Referenced, Archived} (lines 81–101) **and** a
  separate Status vocabulary {Draft, Generated, Validated, Approved, Published,
  Archived} (lines 301–311) — two overlapping but non-identical vocabularies for
  one object's progression. The Artifact also carries an "Evidence" field that
  overlaps the standalone Evidence object (02, 14).
- **Where it appears.** Artifact Model (17), Object Model (02), Validation (14).
- **Impact if unresolved.** The Artifact schema (`AP-111`) would carry two
  progression vocabularies and an Evidence field competing with the canonical
  Evidence object; lineage and validation references become ambiguous.
- **Resolution owner.** `AP-111`.
- **Status.** Open.

#### G12 — Policy Engine: Condition Language + Specificity + Decision-Type Overlap Undefined
- **Severity.** Medium.
- **Description.** The Policy Engine (20) leaves the condition/constraint
  expression language undefined; the "Specificity" term used in conflict
  resolution is never computed or defined; its Decision Types (Retry / Escalate /
  Abort / Delay) overlap Recovery's strategy semantics with no boundary; and a
  "Default Policy" is referenced but never defined.
- **Where it appears.** Policy Engine (20); overlaps Recovery (19).
- **Impact if unresolved.** The Policy Engine runtime (`AP-205`) cannot
  implement a testable specificity rule or a deterministic conflict-resolution
  order; policy and recovery decision spaces collide.
- **Resolution owner.** `AP-004` (language + specificity decision); `AP-205`
  (runtime) (→ ADR-004).
- **Status.** Open.

### Low

#### G15 — Documentation Hygiene (Stale Index + Triple-Named Doc 13)
- **Severity.** Low.
- **Description.** The `docs/v2/README.md` index is stale (reflects an older,
  smaller doc set and wrong numbering; omits 16–26). Doc 13 carries three names:
  the file is `13_EXECUTION_MODEL.md`, the title/body says "Execution Strategy,"
  and the index labels it "EXECUTION_STRATEGY."
- **Where it appears.** `README.md`, doc 13.
- **Impact if unresolved.** A new engineer cannot trust the index; the
  triple-naming obscures which document defines the Execution Strategy object.
  No runtime consequence.
- **Resolution owner.** `AP-007`.
- **Status.** Open.

---

## Gap → Resolution Owner → ADR Summary

| Gap | Title | Severity | Status | Owner AP(s) | ADR(s) |
|-----|-------|----------|--------|-------------|--------|
| G1  | Persistence / event-sourcing model undecided | Critical | Open | AP-001 | ADR-001 |
| G2  | Registry convergence (Harness·Runtime·Resource·Capability) | High | Open | AP-002 | ADR-002 |
| G3  | Work Package defined 3× | High | Open | AP-003, AP-105 | ADR-003 |
| G4  | Execution Graph containment + redundant Dependency Graph | High | Open | AP-003, AP-104 | ADR-003 |
| G5  | Observation dual-owned | High | Open | AP-003, AP-110 | ADR-003 |
| G6  | Intent Resolution == Executive Intelligence | High | Open | AP-003, AP-007 | ADR-003 |
| G7  | Goal object never structurally defined | High | Open | AP-102, AP-003 | ADR-003 |
| G8  | Approval taxonomy mismatch | High | Open | AP-004 | ADR-004 |
| G9  | Validation enum drift | Medium | Open | AP-112, AP-502 | ADR-008 |
| G10 | Resource state contradiction (two state machines) | High | Open | AP-002, AP-003, AP-109, AP-203 | ADR-002, ADR-009 |
| G11 | Artifact status vs. lifecycle + Evidence overlap | Medium | Open | AP-111 | ADR-008 |
| G12 | Policy condition language / specificity / decision overlap | Medium | Open | AP-004, AP-205 | ADR-004 |
| G13 | Dual ownership of recovery + validation strategy | High | Open | AP-003, AP-004, AP-107 | ADR-003, ADR-004 |
| G14 | Determinism asserted over non-deterministic steps | High | Open | AP-004 | ADR-004 |
| G15 | Doc hygiene (stale index, triple-named doc 13) | Low | Open | AP-007 | — |

The four Phase-0 ADRs (ADR-001…ADR-004) must be **Accepted** before Phase 1
begins. Gaps G9 and G11 are enforced through Phase 1 schema work and recorded
under the object-model reconciliation ADRs (ADR-008/ADR-009); they do not each
require a separate foundational decision but are tracked to closure. See
`09_ADR_BACKLOG.md` for the full decision records and the closing traceability
table.
