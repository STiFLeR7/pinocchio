# Contract — Context Package

Status: Frozen (Phase 0 contract freeze)
Object: Context Package
Primary source: `docs/v2/03_CONTEXT_ENGINEERING.md`
Binding ADRs: ADR-003 (canonical object model; §7 Context-by-reference), ADR-001
(event-sourced state)

> Logical contract only. No serialization, storage, transport, schema, or code.
> Field lists are logical (name + meaning + required/optional).

---

## 1. Purpose

A Context Package is the **complete operational understanding required to act on a
Goal**: all information discovered, validated, enriched, organized, and packaged by
Context Engineering. It exists so that execution quality is no longer limited by
manually assembled prompts — Nexus answers "what information is required to accomplish
this Goal successfully?" and freezes that answer as a single object (doc 03 *Purpose*,
*Why Context Engineering Exists*).

It does one job: turn incomplete operator intent (a Goal) into minimal, complete,
validated context that Planning can consume. It never plans, selects runtimes,
executes, validates execution, or performs recovery (doc 03 *Architectural
Boundaries*).

---

## 2. Ownership

- **Produced by / owned by:** the **Context Engineering** layer. It is the only
  producer of this object.
- **State transitions owned by:** Context Engineering. It may continuously enrich the
  package as new information becomes available (doc 03 *Continuously Enriched*);
  consumers do not mutate it.
- **Consumed by:** Planning (`plan.md`) as its input; embeddable inside a Work Package
  (`work_package.md`) as that package's Context (ADR-003 §3.2).
- **Knowledge boundary (INV-06).** Context Engineering *consumes* Knowledge
  (`knowledge.md`) read-only; it never owns it.
- Carries **no** provider/runtime/health state (ADR-002) — it may *describe* available
  runtimes/tools as Resource context, but embeds no live provider state. Defines no
  independent authoritative state store (ADR-001).

---

## 3. Lifecycle

State is a **projection of the event log** (ADR-001; INV-14), not a stored
authoritative machine; each transition emits exactly one event (INV-15). The package
follows the Context Lifecycle (doc 03): Discover → Collect → Validate → Enrich →
Organize → Package. Logical states:

- **Assembling** — context is being discovered, collected, and enriched from sources
  (workspace, knowledge, operator, runtime, environment).
- **Validating** — completeness, consistency, availability, freshness, authorization,
  and quality are being evaluated (doc 03 *Context Validation*).
- **Ready** — validated and packaged; available to Planning. May still be re-enriched
  (Ready → Enriching → Ready) as execution surfaces new information.
- **Enriching** — a Ready package is being updated with newly available information
  (doc 03 *Continuously Enriched*); produces a new version (see §8) and returns to
  Validating/Ready.
- **Superseded** — replaced by a newer version of the same Goal's Context Package.
  Terminal for that version.
- **Invalidated** — found incomplete/conflicting and withdrawn from planning use until
  re-assembled. Terminal for that version.

Allowed transitions: Assembling → Validating → Ready; Ready → Enriching → Validating;
Validating → Invalidated; any version → Superseded on re-version. Non-deterministic
discovery/enrichment values are captured as event data (INV-17).

---

## 4. Required Fields

- **identity** — stable, unique identifier; addressable, correlatable, replayable.
- **goal_ref** — reference (by id) to the single Goal (`goal.md`) this package serves.
  Exactly one Goal per Context Package (and one Context Package per Goal).
- **correlation** — correlation / trace lineage shared with the Goal and downstream
  objects, so context provenance is auditable.
- **context_categories** — the **eight Context Categories** (doc 03), each a logical
  section of the package:
  - **goal_context** — objective, desired outcome, success definition.
  - **domain_context** — operational domain, terminology, knowledge requirements,
    standards.
  - **workspace_context** — operational environment: repositories, files, documents,
    communication channels.
  - **historical_context** — previous work, failures, executions, decisions.
  - **operational_context** — current state, running workflows, open tasks, priorities,
    dependencies.
  - **constraint_context** — governance, security, deadlines, approvals, quality
    expectations, budgets.
  - **resource_context** — available runtimes, tools, knowledge, skills (described, not
    live provider state).
  - **execution_context** — validation requirements, expected outputs, execution
    assumptions, dependencies.
- **constraints** — the operative constraints governing work on this Goal (doc 03
  *Context Packaging*). Constraints always override execution preferences.
- **resources** — the resources (runtimes, tools, knowledge, skills) available to
  accomplish the Goal, by reference; described capability, not live provider/health
  state (ADR-002).
- **confidence** — Context Engineering's confidence that the assembled context is
  sufficient and correct.
- **validation_status** — the outcome of context validation (completeness,
  consistency, availability, freshness, authorization, quality). Indicates whether the
  package is fit for Planning.
- **status** — the projected lifecycle state (§3). Derived, never authoritative.

---

## 5. Optional Fields

- **supporting_artifacts** — references to artifacts that inform the work (e.g.,
  documents, prior reports, ADRs). Referenced by id, not embedded
  (relates to `artifact.md`).
- **references** — links/pointers to external or internal sources used to build the
  context (provenance trail), distinct from supporting artifacts.
- **known_unknowns** — explicitly identified gaps: missing information, open
  assumptions, unresolved dependencies, evidence that will eventually be required
  (doc 03 *Context Discovery*, *Context Packaging*). Surfaced rather than hidden.
- **enrichment_history** — record of enrichment passes applied to the package, for
  explainability and freshness reasoning.
- **freshness** — recency indicators for time-sensitive context elements.
- **source** — provenance summary of where the context was gathered (workspace,
  knowledge, operator, runtime, environment).

> **Goal Context vs. Goal object.** The `goal_context` category *describes* the Goal's
> objective/outcome/success for planning convenience; it does not redefine or override
> `goal.md`, which remains the single canonical Goal (INV-07).

---

## 6. Invariants

- **Exactly one Context Package per Goal** (doc 02 *Context Package*; doc 03). The
  `goal_ref` is single-valued; no Goal has two Context Packages and no package serves
  two Goals.
- **INV-06.** The package consumes Knowledge read-only; Context Engineering never owns
  or mutates Knowledge.
- **INV-07.** One canonical Context Package schema; no subsystem introduces an
  alternative representation of operational context.
- **INV-12 / evidence boundary.** The package references Evidence/artifacts by id and
  never embeds Evidence; it carries context, not validation verdicts.
- **Minimal complete context** (doc 03). The package aims for sufficiency, not
  excess; `known_unknowns` must surface gaps rather than allow silent assumptions.
- **No procedural content.** The package describes *what is known and required*, not
  *how to execute*; it never contains a Plan or runtime selection (doc 03
  *Architectural Boundaries*; preserves INV-03/INV-08 at the context seam).
- **Provider independence (ADR-002).** Resource/runtime entries are described
  capabilities by reference; no live provider/health/availability state is embedded
  (that lives only in the Harness Registry).
- **INV-13 / INV-14 / INV-15.** State and any snapshot are projections of the
  authoritative event log; each transition emits exactly one event.
- **INV-17.** Non-deterministic discovery/enrichment outputs are captured as recorded
  data, never recomputed on replay.

---

## 7. Relationships

- **Belongs to →** exactly one `goal.md` (via `goal_ref`); produced from that Goal.
- **Consumes (read-only) →** `knowledge.md` (INV-06); references `resource.md` and
  `skill.md` as available resources/skills; references `artifact.md` as supporting
  artifacts.
- **Consumed by →** `plan.md` (the package is Planning's input).
- **Embeddable in →** `work_package.md` as that package's Context (ADR-003 §3.2).
  **Context-by-reference option:** for large packages, a Work Package may reference the
  Context Package by id rather than embedding it (ADR-003 §7, tracked as sanctioned
  debt to avoid Work Package bloat); the embedding-vs-reference choice is a
  Work Package concern and does not change this object's definition.
- **Correlation lineage:** shares trace identity with the Goal and all downstream
  objects.

---

## 8. Versioning Rules

- **Additive evolution only.** New optional fields and new context-source descriptors
  may be added compatibly (e.g., semantic context graphs, context scoring — doc 03
  *Future Evolution*). The eight Context Categories are the stable canonical set;
  growth happens *within* categories or as new optional fields, not by forking the
  object.
- **Enrichment produces versions, not in-place rewrites of history.** Continuous
  enrichment yields a new package version tied to a log position; prior versions remain
  replayable and become **Superseded**, never destructively overwritten (ADR-001
  append-only; INV-14).
- **Published shape is immutable.** Existing field meanings never change in place;
  packages remain replayable forever via event upcasting (ADR-001).
- **Required set is stable.** Changing the required set (e.g., dropping a Context
  Category) requires a new object version and a superseding ADR; old packages remain
  replayable under their original version.
- **Determinism preserved.** Any new field influencing context assembly must be
  captured as recorded data so replay stays deterministic (INV-17).
