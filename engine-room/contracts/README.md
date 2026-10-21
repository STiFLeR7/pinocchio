# Nexus v2 — Canonical Logical Contracts

Status: Frozen (Phase 0 contract freeze)
Authority: These are the **canonical logical definitions** of the Nexus
operational objects. They are the single source of truth referenced by
`blueprint/v2/02_ACTION_POINTS.md` Phase 1 (AP-101…AP-112) and enforced by the
contract-test harness (AP-006).

---

## What These Are — and Are Not

A contract here is an **implementation-independent logical specification** of an
architectural object. It defines *what the object is, who owns it, how it lives,
what it must contain, what must always be true of it, how it relates to other
objects, and how it may evolve.*

A contract is **not**:
- a serialization format (JSON/Proto/Avro are out of scope — deferred),
- a database schema or storage design,
- an API or network protocol,
- code, types, or pseudo-code.

Field lists are **logical** (name + meaning + required/optional), never typed
wire definitions. Serialization is chosen later, governed by ADR-001 and the
Phase-1 schema-format Action Point (AP-101).

## Fixed Template

Every contract document uses these eight sections, in order:

1. **Purpose** — why the object exists; the one job it does.
2. **Ownership** — which layer produces it and which layer(s) own its state
   transitions (per the Object Model and ADR-003).
3. **Lifecycle** — the states it moves through and the transitions allowed
   (state is a projection of the event log, per ADR-001).
4. **Required Fields** — logical fields that must always be present.
5. **Optional Fields** — logical fields that may be present.
6. **Invariants** — statements that must always hold (cross-referenced to
   `docs/v2/99_ARCHITECTURAL_INVARIANTS.md` `INV-xx`).
7. **Relationships** — which other contracts it references, embeds, or is
   referenced by (by contract name).
8. **Versioning Rules** — how the object may change compatibly over time.

## Cross-Cutting Rules (bind every contract)

- **Single source of truth (ADR-001).** The Event Log is authoritative. Any
  object's *current state* is a derived projection; *checkpoints* are derived
  snapshots. No contract may define an independent, authoritative state store.
- **One schema per object (ADR-003, INV-07).** No object is defined twice; no
  subsystem introduces an alternative representation.
- **Identity & correlation.** Every operational object has a stable identity and
  participates in a correlation/trace lineage so it is replayable and auditable.
- **Provider independence (ADR-002).** No object above the Harness boundary
  embeds provider/runtime/health state; that lives only in the Harness Registry.
- **Evidence over confidence (INV-20/INV-12).** Completion-related objects derive
  truth from Evidence, never from runtime self-report.
- **Versioning is additive.** Compatible evolution adds optional fields or new
  versions; published event/object types are never mutated in place (ADR-001
  event upcasting).

## Contract Index

| Contract | Object | Primary source | Binding ADRs |
|----------|--------|----------------|--------------|
| `intent.md` | Operator request / resolved intent | `16` | ADR-003 |
| `goal.md` | Goal | `02`, `16` | ADR-003 |
| `context_package.md` | Context Package | `03` | ADR-003 |
| `plan.md` | Plan | `02`, `04` | ADR-003 |
| `work_package.md` | Work Package | `05`, `04` | ADR-003 |
| `execution_strategy.md` | Execution Strategy | `13` | ADR-004 |
| `execution_graph.md` | Execution Graph | `18` | ADR-003 |
| `skill.md` | Skill | `06` | ADR-002, ADR-004 |
| `capability.md` | Capability | `21` | ADR-002 |
| `resource.md` | Resource | `22` | ADR-001, ADR-002 |
| `artifact.md` | Artifact | `17` | ADR-003 |
| `observation.md` | Observation | `09` | ADR-003 |
| `event.md` | Event | `23` | ADR-001 |
| `checkpoint.md` | Checkpoint | `25` | ADR-001 |
| `policy.md` | Policy | `20`, `12` | ADR-004 |
| `knowledge.md` | Knowledge Entry | `10` | ADR-001, ADR-003 |
| `reflection.md` | Reflection | `26` | ADR-003 |

> Note: `state` is not a separate contract — per ADR-001 it is a projection of
> `event.md`; each object's Lifecycle section defines its states. The Validation
> Report is defined within `work_package.md`/`observation.md` relationships and
> the Validation layer; it may be promoted to its own contract if Phase 1 needs.
