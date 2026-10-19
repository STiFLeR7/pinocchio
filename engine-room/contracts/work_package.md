# Work Package — Canonical Logical Contract

Status: Frozen (Phase 0 contract freeze)
Primary source: `docs/v2/05_WORK_PACKAGES.md`, `docs/v2/04_PLANNING.md`
Binding: ADR-003 (§3.2 the single authoritative Work Package schema), ADR-001
(state is projection), ADR-004 (approval/validation/recovery policy lives on
Execution Strategy, not duplicated here)

> Logical specification only. No serialization, storage, API, or code. Fields are
> logical (name + meaning + required/optional).

---

## 1. Purpose

A **Work Package** is the smallest complete, independently executable unit of
operational work in Nexus. It contains *everything required for reliable
execution* — objective, context, constraints, resources, skills, inputs,
expected outputs, evidence requirements, and completion criteria — while
remaining independent of any execution technology.

The Work Package is the bridge between the operator's world of Goals and the
runtime's world of actions. Runtimes never receive Goals or raw operator
requests; they receive Work Packages (INV-09 / INV-19). It is the single unit of
execution throughout the platform.

Per ADR-003 §3.2 this is **the one authoritative Work Package schema**. The
Planning document's field names ("required capabilities", "validation
requirements") are *mappings into* this schema, not a second definition: required
capabilities resolve into `Skills` + capability references; validation
requirements resolve into `Evidence` + `Completion Criteria`.

---

## 2. Ownership

- **Produced by:** Planning. Planning is the only producer of Work Packages
  (INV-04 — Execution never plans; INV-09 — Work Packaging is the sole producer
  of the runtime contract).
- **State owned by:** Shared along the lifecycle but single-owner per phase —
  Planning owns creation and `Created`/`Ready`; Orchestration owns the
  execution-control transitions (`Executing`/`Paused` via pause/resume/cancel,
  INV-23); Validation owns the completion decision (`Completed`, INV-20/INV-21);
  Recovery influences `Blocked`/`Failed` continuation (INV-22). All transitions
  are events on the authoritative log (ADR-001).
- **Consumed by:** Execution (executes the assigned package), Orchestration
  (schedules and controls), Supervision (observes), Validation (decides
  completion), Recovery (decides continuation).
- **Boundary:** A Work Package never performs execution, creates Plans, selects
  runtimes, or validates its own evidence (doc 05 boundaries; INV-21).

---

## 3. Lifecycle

State is a projection of the Event Log (ADR-001, INV-13/INV-14); every transition
emits exactly one Event (INV-15). The Work Package is checkpoint-aware (INV-18):
it resumes from its latest checkpoint plus event replay, never from the Goal.

| State | Meaning |
|-------|---------|
| `Created` | Planning has produced the package; not yet cleared for execution. |
| `Ready` | All preconditions met (context complete, dependencies satisfied); eligible for orchestration. |
| `Executing` | A runtime is performing the work under Orchestration control. |
| `Paused` | Execution suspended by Orchestration (e.g. awaiting approval, supervision-recommended pause). |
| `Completed` | Validation has decided completion from sufficient Evidence (INV-20). |
| `Blocked` | Cannot proceed (unsatisfied dependency, unavailable resource, pending approval). |
| `Cancelled` | Terminated by Orchestration/Governance before completion. |
| `Failed` | Execution could not produce a completable outcome and recovery does not continue it. |
| `Expired` | A deadline/timeout constraint elapsed before completion. |

Allowed transitions (representative):

```
Created → Ready → Executing → Completed
Ready → Blocked | Cancelled | Expired
Executing → Paused → Executing
Executing → Blocked | Failed | Cancelled | Expired
Paused → Cancelled | Expired
Blocked → Ready | Cancelled | Expired
```

- **Completion is never self-declared.** Execution exposes outputs and Evidence
  Candidates; Validation alone moves the package to `Completed` (INV-20/INV-21).
- **Control is Orchestration's.** Pause/resume/cancel are Orchestration
  transitions; Supervision only recommends (INV-23).

---

## 4. Required Fields

Grouped per the authoritative structure (ADR-003 §3.2 / doc 05).

### Identity
| Field | Meaning |
|-------|---------|
| `identifier` | Stable unique id; participates in correlation/trace lineage. |
| `parent_goal` | Reference (by id) to the originating Goal. |
| `parent_plan` | Reference (by id) to the owning Plan. |
| `priority` | Relative execution priority assigned by Planning. |

### Objective
| Field | Meaning |
|-------|---------|
| `objective` | The single desired outcome and operational purpose of this package. Self-describing: understandable without the original operator request. One objective only (atomicity). |

### Context
| Field | Meaning |
|-------|---------|
| `context` | The operational context required for execution: an **embedded Context Package** (`context_package.md`) plus supporting artifact references and dependency references. May be carried **by reference** for large packages (see §8). Execution must not need to discover missing context. |

### Constraints
| Field | Meaning |
|-------|---------|
| `constraints` | Governance, approvals, deadlines, budgets, and quality requirements bounding the work. Constraints override execution preferences. Governance/approval semantics are *evaluated* against Policy and the Execution Strategy, not re-implemented here. |

### Resources
| Field | Meaning |
|-------|---------|
| `resources` | Declares *available* resources/capabilities for the work (e.g. runtimes, tools, workspaces). Describes availability, **not selection** — runtime selection is Orchestration's (INV-37). |

### Skills
| Field | Meaning |
|-------|---------|
| `skills` | References to required Skills plus capability references. This is where Planning's "required capabilities" resolve (ADR-003 §3.2). Skills describe operational capability, not runtime implementation (INV-33). |

### Inputs
| Field | Meaning |
|-------|---------|
| `inputs` | The required information/artifacts the work consumes (repositories, documents, prior outputs, references). |

### Outputs
| Field | Meaning |
|-------|---------|
| `outputs` | The expected deliverables (reports, source code, documentation, pull requests, summaries). Declares what should be produced, not the produced artifacts themselves. |

### Evidence
| Field | Meaning |
|-------|---------|
| `evidence` | How completion is verified: the evidence requirements the work must satisfy. Execution produces **Evidence Candidates**; Validation promotes them to **Evidence** (INV-12). This field declares the requirement; the package references resulting Evidence by id and never embeds it. |

### Completion Criteria
| Field | Meaning |
|-------|---------|
| `completion_criteria` | The conditions that define success. Completion derives from Evidence, never from runtime confidence/self-report (INV-20). |

### Status
| Field | Meaning |
|-------|---------|
| `status` | The projected lifecycle state (§3). |

---

## 5. Optional Fields

### Checkpoints
| Field | Meaning |
|-------|---------|
| `checkpoints` | References to checkpoints created during the package's life (e.g. Planning Complete, Context Ready, Execution Started/Paused/Resumed, Validation Complete). Each checkpoint is a derived snapshot tied to a log position (ADR-001); enables recovery (INV-18). |

### Observability
| Field | Meaning |
|-------|---------|
| `observability` | What the package exposes for supervision: current state, progress, elapsed time, active runtime, evidence collected, artifacts generated. Supports observability invariants (INV-38). |

### Other optional
| Field | Meaning |
|-------|---------|
| `dependencies` | References to other Work Packages this one depends on. Authoritative ordering lives as **edges in the Execution Graph** (INV-10); this is a convenience reference, not the ordering authority. |
| `execution_strategy_ref` | Reference to the governing `execution_strategy.md` (coordination/approval/retry/timeout/validation/recovery/checkpoint policy). The package carries policy by reference, not by duplication (ADR-004 precedence). |
| `evidence_refs` | References (by id) to promoted Evidence produced for this package. |
| `correlation` | Correlation/trace identifiers tying the package to its Goal/Plan lineage. |
| `estimates` | Per-package complexity/effort/duration estimates carried from Planning. |

---

## 6. Invariants

- **INV-07 / ADR-003 §3.2:** Exactly one Work Package schema. `04`, `05`, and
  `14` all bind to this definition; no alternative representation exists. "Required
  capabilities" → `skills` + capability refs; "validation requirements" →
  `evidence` + `completion_criteria`.
- **INV-09 / INV-19:** Runtimes receive Work Packages — never Goals, never raw
  operator requests. Planning (Work Packaging) is the sole producer.
- **INV-04 / INV-21:** A Work Package never plans, never selects its runtime, and
  never declares its own completion.
- **INV-20:** Completion is determined from independently verifiable Evidence;
  runtime "success" with insufficient evidence does not complete the package.
- **INV-12:** Execution produces Evidence Candidates; Validation produces
  Evidence. The package references Evidence by id and never embeds it.
- **INV-13 / INV-14 / INV-15:** State is a projection of the authoritative Event
  Log; every transition emits exactly one Event; checkpoints are derived.
- **INV-18:** Every execution is checkpoint-aware; resume is from latest
  checkpoint + replay, never from the Goal.
- **INV-33 / INV-37:** Skills are runtime-independent; `resources` describe
  availability, not selection (selection is Orchestration's).
- **Atomicity:** Exactly one objective per package.

---

## 7. Relationships

- **References `goal.md`** (`parent_goal`) and **`plan.md`** (`parent_plan`) by
  id. Plans own Work Packages; the inverse is forbidden.
- **Embeds (or references) `context_package.md`** via `context`.
- **References `skill.md`** and `capability.md` via `skills`.
- **References `execution_strategy.md`** via `execution_strategy_ref`; the
  Strategy governs coordination/approval/retry/timeout/validation/recovery/
  checkpoint policy for the package.
- **Referenced by `execution_graph.md`:** each graph Node references a Work
  Package; graph edges express the authoritative dependencies between packages.
- **References `evidence`/`artifact.md`/`checkpoint.md`** by id (never embeds
  Evidence; Artifacts reference Evidence by id per ADR-003 §3.7).
- **Observed via `observation.md`:** Supervision derives Observations from the
  package's exposed observability; Execution emits raw Execution Events only
  (INV-11).
- **Governed by `policy.md`:** constraints/approvals are evaluated by the Policy
  Engine (INV-28), not hardcoded in the package.

---

## 8. Versioning Rules

- **Additive evolution.** New optional fields (e.g. nested sub-packages, reusable
  template references, adaptive-checkpoint metadata — all deferred in doc 05) are
  added without breaking the schema. Required grouped fields are never removed or
  repurposed in place.
- **Context-by-reference is a sanctioned variant.** To avoid embedded Context
  Package bloat (ADR-003 §7 / R-7), the `context` field may carry the Context
  Package **by reference** instead of by embedding for large packages. Embedding
  vs. reference is a representation choice; the logical contract (context must be
  complete and available to execution) is unchanged.
- **One definition forever.** Future evolution extends this single schema; it
  never introduces a parallel Work Package object (INV-07). v1 task records map
  into this schema during migration (ADR-003 §9).
- **Immutable history.** A finalized package's state changes are appended as
  events; past states remain reconstructable (ADR-001). Identity is stable across
  the package's lifecycle.
