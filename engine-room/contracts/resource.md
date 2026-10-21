# Resource — Canonical Logical Contract

Status: Frozen (Phase 0 contract freeze)
Object: Resource · Primary source: `docs/v2/22_RESOURCE_MODEL.md` · Binding ADRs: ADR-001, ADR-002

> A logical, implementation-independent specification. Fields are logical
> (name + meaning + required/optional), never wire/typed definitions. No
> serialization, storage, API, or code is implied here.

---

## 1. Purpose

A Resource is an **allocatable instance** — a concrete operational asset that can
be assigned to a Work Package and consumed during execution (an AI runtime, a
human operator, a repository/filesystem, a communication channel, a compute or
budget quota). Where a Capability is *what can be done* (`capability.md`), a
Resource is *what is currently available to do it*.

Per ADR-002, the Resource is **not a discovery registry**. Discovery of
harness-backed providers (their advertised capabilities, availability, health) is
owned by the **Harness Registry**. The Resource object's job is **allocation**:
representing an instance and the **allocation state projection** by which
Orchestration tracks who holds what, when.

---

## 2. Ownership

- **Produced by:**
  - **Harness-backed Resources** — projected from the **Harness Registry** (the
    sole source of provider identity/capabilities/availability/health, ADR-002).
    The Resource references the Harness; it never copies provider state.
  - **Infrastructure Resources** (non-harness quotas: compute, budget,
    human-time windows) — catalog entries in a thin **Infrastructure Resource
    catalog** (an allocation ledger, ADR-002), **not** a discovery registry.
- **Allocation state owned by:** **Orchestration**, the **sole allocator**
  (ADR-002). Allocation state (Allocated / Reserved / Released) is a **projection
  in the unified State Model** (ADR-001) — a deterministic fold over allocation
  events, never an independent state store.
- **Consumed by:** Execution (consumes allocated Resources via its Work Package),
  Supervision (observes health/utilization — read from the Harness Registry for
  harness-backed Resources), Recovery (requests restoration of availability via
  Orchestration).
- **Explicitly NOT owned here:** Planning. **Planning never allocates** (INV-03;
  `22`). Planning may *request* resources by Capability; allocation is
  Orchestration's exclusively. Provider availability/health is **not owned here**
  — it is read from the Harness Registry (INV-36).

---

## 3. Lifecycle

Per ADR-001 §3.4, Resource availability is **one specialized projection in the
unified State Model**, *not* a separate independent state machine. Every
transition emits exactly one Event (INV-15) and is rebuildable from the log.

**Allocation projection (owned by Orchestration):**

```
Available → Reserved → Allocated → Released → Available
```

- **Available** — eligible for allocation.
- **Reserved** — tentatively held by Orchestration pending commitment.
- **Allocated** — committed to a specific Work Package (assignment is temporary;
  the Resource remains independent — `22`).
- **Released** — returned to the pool, projecting back to Available.

**Availability projection (specialized vocabulary of the same lifecycle, ADR-001
§3.4; for harness-backed Resources these values are *read from the Harness
Registry*, not authored here):**

```
Available · Busy · Reserved · Offline · Maintenance · Failed · Unknown
```

**Failure / recovery path** (transitions are events, not a second machine):

```
Allocated → Failed/Offline → (Recovery via Orchestration) → Available
```

> Reconciliation (G10): doc-22's availability states and doc-24's generic
> lifecycle are **the same machine**; doc-22's vocabulary is a specialized
> projection over it. There is exactly one Resource state machine (INV-07).

---

## 4. Required Fields

| Field | Meaning |
|-------|---------|
| **Identity** | Stable, unique identity of the Resource instance; participates in correlation/trace lineage so allocation is replayable and auditable. |
| **Type / Category** | Logical class of asset (e.g. Human, AI/Runtime, Workspace, Communication, Infrastructure, Knowledge, Compute) — for allocation reasoning, not provider implementation. |
| **Allocation State** | The current allocation-projection value (Available / Reserved / Allocated / Released). A **projection** of allocation events (ADR-001); never an authoritative independent store. Owned operationally by Orchestration. |
| **Capability Reference** | For harness-backed Resources: a **reference** to the advertised Capabilities **in the Harness Registry**. The Resource never duplicates capability definitions or provider capability lists (ADR-002). |
| **Backing Reference** | Identifies what backs the instance: either the **Harness** (Harness Registry identity, for harness-backed Resources) **or** the Infrastructure Resource catalog entry (for non-harness quotas). Exactly one applies. |

---

## 5. Optional Fields

| Field | Meaning |
|-------|---------|
| **Owner** | The accountable owner/holder of the instance (operational ownership, not allocation holder). |
| **Constraints** | Allocation-influencing boundaries: concurrency limits, execution limits, security restrictions, budget limits, time windows, workspace permissions, operational policies (`22`). |
| **Operational Limits** | Quota/capacity figures relevant to allocation accounting (esp. Infrastructure Resources: compute, budget, human-time). |
| **Utilization** | Allocation-relevant utilization/accounting (concurrent allocations, consumed quota). Live performance utilization for harness-backed Resources is read from the Harness Registry, not owned here. |
| **Relationships** | Explicit dependencies on other Resources (e.g. a runtime that requires a filesystem/repository/network) — `22`. References by Resource Identity. |
| **Allocation Holder** | When Allocated/Reserved: the Work Package (and correlation) currently holding the instance. |
| **Metadata** | Non-authoritative descriptive attributes (tags, notes, documentation links). |

> **Deliberately excluded** (assigned to the Harness Registry as sole owner —
> ADR-002, INV-36): provider **Availability**, **Health**, **Authentication**,
> **Configuration** for harness-backed Resources. The Resource references these;
> it never stores or duplicates them.

---

## 6. Invariants

- **INV-36** — One source of truth for provider availability and health: the
  Harness Registry. Harness-backed Resources **reference** it and never
  duplicate availability/health. A Runtime is a Harness of category Runtime.
- **INV-32** — Resource references abstract Capabilities (via the Harness
  Registry); it carries no provider-independent capability *definitions* (those
  live in `capability.md`).
- **INV-13 / INV-14 / INV-15** — Allocation state is a **derived projection** of
  the append-only Event Log; it is never authoritative and never an independent
  store; every allocation transition emits exactly one Event.
- **ADR-001 §3.4** — Resource availability is one specialized projection of the
  unified State Model, **not** a separate state machine (resolves G10).
- **INV-03** — Planning never allocates; Orchestration is the **sole allocator**.
- **INV-16** — Allocation consumers are idempotent: duplicate/out-of-order
  allocation events cause no duplicate state change (dedup by event identity).
- **INV-07** — Exactly one canonical Resource schema; the Infrastructure catalog
  and harness-backed projection are the **same** object, not alternatives.
- **Single backing** — exactly one of {Harness backing, Infrastructure catalog
  backing} applies to any Resource instance.

---

## 7. Relationships

- **`capability.md`** — A Resource *provides* Capabilities, but only by
  **reference through the Harness Registry**; it never embeds Capability
  definitions. Resources answer "who/what can do it"; Capabilities answer "what."
- **Harness Registry** (Harness SDK spec; not a contract file here) — the sole
  owner of provider identity/capabilities/availability/health for harness-backed
  Resources. The Resource is an allocation **projection over** registered
  Harnesses. A Runtime Resource is a Harness of category Runtime (no separate
  Runtime registry — ADR-002).
- **`work_package.md`** — Orchestration **allocates** Resources to Work Packages;
  the allocation holder references the Work Package. Execution consumes the
  allocated Resource (Execution never allocates — INV-04).
- **`execution_strategy.md`** — declares coordination/concurrency behavior that
  Orchestration enacts when reserving/allocating Resources; the Strategy itself
  never allocates (INV-05).
- **`event.md`** — every allocation/availability transition is an Event with
  correlation and trace identity (INV-39); the projection folds these events.
- **`observation.md`** — Supervision observes Resource health/utilization (read
  from the Harness Registry) and emits Observations; it recommends, Orchestration
  acts (INV-23).

---

## 8. Versioning Rules

- Evolution is **additive**: new optional fields, new Resource Types/Categories,
  new Constraint kinds — without breaking existing allocation consumers.
- The **allocation-projection vocabulary** (Available/Reserved/Allocated/
  Released) and the availability vocabulary are versioned additively; new states
  must reconcile as projections of the unified State Model, never as a new
  independent machine (ADR-001 §3.4).
- Allocation transition **events are append-only and backward-compatible**
  (event upcasting, ADR-001): historical allocation history stays replayable
  forever.
- Adding a **Backing Reference** kind (e.g. a future remote/sandboxed Harness, or
  a new Infrastructure quota class) is additive and must not change the
  single-backing invariant or move availability/health ownership off the Harness
  Registry.
- The Resource schema is **never duplicated**; any new resource-like concept must
  reuse this contract or supersede it via ADR (INV-07).
