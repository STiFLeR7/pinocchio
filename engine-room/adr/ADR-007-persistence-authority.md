# ADR-007 — Persistence Authority

- **Status:** Accepted (Phase 0, ratified)
- **Date:** 2026-07-13
- **Deciders:** Architecture Review Board
- **Relates:** ratifies `docs/v2/P0_ADR007_PERSISTENCE_SPIKE.md`; depends on ADR-001 (Event is authoritative; State is a projection); informs `contracts/event.md`, `contracts/checkpoint.md`, and `nexus_core/persistence/interfaces.py`. Closes readiness condition **C1** (`IMPLEMENTATION_READINESS_REVIEW.md`) and hidden decisions **H1/H2**. Front-loaded per **C6**.
- **Affected work:** Engineering Program **P1** (Durable Foundation) — WP-P1.1/1.2/1.3; enables **P2/P3** and the entire spine.
- **Numbering note:** filed in the v2 constitutional `adr/` series at 007. This is distinct from `blueprint/DECISIONS/ADR-007-email-provider.md` (a legacy v1-era series); the collision is resolved by series, and "ADR-007" hereafter denotes this decision in the v2 series.

---

## 1. Context

ADR-001 ratified that Nexus is event-sourced: the append-only Event Log is the single authoritative source of operational truth, and current State is a materialized projection. The v2 substrate implements that seam correctly — an authoritative `EventStore`, a `ProjectionEngine` that folds the log into read models, snapshot-plus-replay recovery, idempotent append, and a determinism seam that records non-deterministic values as event data — **but entirely in memory** (`nexus_infra/event_store.py`, `projections.py`, `snapshots.py`). Truth in v2 is authoritative yet volatile: a Python list lost on process exit.

The durable store that already exists lives in v1: SQLite via async SQLAlchemy (`nexus/database.py`), where entity state is a mutable row UPDATEd in place and an `audit_log` event is written *after* the mutation as a side record. v1 is CRUD/state-authoritative with an audit ledger — not event-sourced.

Every "Nexus thinks" capability depends on durable, replayable operational history. The persistence spike established that the durability half of ADR-001 is the highest-leverage unbuilt decision, and that binding v1's store naively under v2's protocols risks an irreversible invariant break.

## 2. Problem Statement

Making v2 durable forces two decisions the Blueprint left implicit (H1/H2), with a real INV-13 risk:

- **H1 — sync/async boundary.** The v2 persistence protocols (`nexus_core/persistence/interfaces.py`) are entirely synchronous (`def`, zero `async def` across all `nexus_*` packages). v1's durable store is asynchronous (`AsyncSession`, `create_async_engine`). A naive reuse forces an async→sync bridge with deadlock risk.
- **H2 — authoritative-store model.** v1's mutable CRUD rows are state-authoritative; ADR-001 and INV-13/14 require the event log to be authoritative and state to be a projection. The Blueprint's Stage-1 phrasing ("bind v2 repos → v1 durable store… no behavior change… share truth") would, read naively, elevate v1's mutable store to authority under an event-sourced platform — which the Readiness Review classifies as an INV-13 **blocker, not a bounded exception**.

The decision must make v2 durable without reversing ADR-001 and without importing async into the synchronous spine.

## 3. Decision

**Durability is added *behind the existing synchronous protocols*, with the append-only Event Log remaining the single authoritative source of truth. v2 stays fully synchronous; there is no async bridge. v1's relational tables are demoted to projections via the transactional-outbox seam ("the outbox becomes the log", ADR-001 §9).**

### 3.1 The durable Event Log is authoritative; v1 tables are projections (H2)

ADR-001's authority model is reaffirmed and made durable: the concrete, persistent `EventStore` is the source of operational truth; current State (including every v1 entity now expressed as a v2 projection) is a deterministic fold of the log. **v1's mutable store is never bound as the authoritative `EventStore` under v2.** A v2 `Repository` is, by its own contract, "a CRUD-free read model" (a projection); binding a read model over v1 data during migration is therefore compatible with INV-13, provided all writes flow through the log. The Blueprint's "share truth / no behavior change" phrasing is superseded by **"share *data* during migration; the Event Log is the sole write authority."**

### 3.2 Durability behind the unchanged synchronous protocols (H1)

The durable `EventStore` is implemented with a **synchronous driver — the standard-library `sqlite3`** — behind the existing sync `EventStore`/`Repository`/`UnitOfWork` protocols. No protocol signature changes; no v2 call site changes. The existing `VersionedSerializer` (envelope + `canonical_json`) is wired to durable storage as the concrete format. Store-assigned positions (`global_sequence`, `stream_position`) are **persisted and never recomputed on load**, so global and per-correlation ordering survive restart. SQLite is the same engine family v1 already uses; a synchronous driver honors the sync protocol natively.

### 3.3 No async bridge; v2 remains synchronous

v2 is **not** made async, and v1's async engine is **not** wrapped under the sync protocols. The async persistence remains confined to the legacy v1 process during coexistence; the v2 durable store is synchronous end-to-end. There is consequently **no sync/async boundary inside v2** to deadlock on.

### 3.4 Transaction, consistency, and recovery

The existing `UnitOfWork` boundary maps to **one durable transaction per commit**: the staged event batch is validated for appendability, then appended and its projections updated **atomically** — a commit never lands a partial batch (the property the in-memory UoW already guarantees, now durable). Projections are **rebuilt on boot** from the nearest valid snapshot plus the replayed tail (`read_from`), never resumed from operator intent (INV-22). Consistency between the log and projections is **transactional (same-commit)**; eventual-consistency variants are out of scope here.

### 3.5 Migration seam: the outbox becomes the log

Migration follows ADR-001 §9. v1's transactional outbox (which already emits events in the same transaction as the state mutation) is the seam: **shadow-only → dual-write → flip reads to v2 projections → make the v2 log authoritative → demote v1 tables to projections → converge-then-delete.** Every step is feature-flag-gated and default-safe (the in-memory store remains the default until the durable store proves parity), and v1 remains the operational system-of-record until its decision is default-on. The dual persistence representation during coexistence is a **declared, time-boxed INV-07 exception** (bounded, per the Readiness Review), closed by converge-then-delete.

## 4. Alternatives Considered

- **A. v1 database remains authoritative (CRUD authority).** *Rejected:* this is precisely ADR-001 §4.A ("Pure state-based CRUD with an event side-channel"), already rejected once; it violates INV-13/14 and is a Readiness blocker. It abandons v2's ratified model and forecloses durable-history capabilities.
- **B. Reuse v1's async store behind the sync protocols via an async→sync bridge.** *Rejected:* unnecessary given a synchronous SQLite driver, and it carries deadlock risk (bridging an event loop under synchronous callers). Managing a hazard that can be deleted is the wrong trade.
- **C. Make the v2 persistence protocols asynchronous.** *Rejected:* zero `async def` exist across ~26.7k LOC of `nexus_*`; the blast radius is the entire synchronous spine, for no benefit — the store is local SQLite, not a network database.
- **D. Pure event sourcing with no materialized projection.** *Rejected:* already rejected by ADR-001 §4.B (hot-path guard-evaluation cost); v2 correctly materializes projections.

## 5. Trade-offs

- **Gain:** one durable source of truth; ADR-001 honored without reversal; the sync/async question dissolved rather than managed; no v2 call-site churn; migration reversible at every step.
- **Cost:** operational complexity of event sourcing made durable (projection rebuild, snapshot cadence, event upcasting, idempotency discipline — accepted by ADR-001 §5); a bounded period of dual persistence representation (INV-07 exception).
- **Accepted because:** long-term correctness (single authoritative history, native replay/recovery/audit) outweighs the transitional cost, and the chosen implementation removes the single hardest risk (the async bridge) instead of carrying it.

## 6. Consequences

- **P1 (Durable Foundation)** builds a synchronous `sqlite3`-backed `EventStore` (WP-P1.1), durable projections + snapshot/rebuild (WP-P1.2), and durable repositories + UoW (WP-P1.3), all behind the unchanged protocols, defaulting off until parity is proven.
- The `InMemoryEventStore` remains the default and the interface-parity oracle: the durable store must pass the existing in-memory test suite unchanged.
- `contracts/event.md` and `contracts/checkpoint.md` remain valid unchanged (Event authoritative; Checkpoint derived) — this ADR adds durability, not schema.
- v1's `memory/*`, and its outbox, are identified as the convergence source and migration seam, not retired until P10.

## 7. Risks

- **R1 — async bleed into the sync spine.** *Mitigation:* synchronous driver; the crossing does not exist; a guardrail keeps `async def` at 0 in `nexus_core`.
- **R2 — v1 store elevated to authority (INV-13 break).** *Mitigation:* the Event Log is the sole write authority; v1 tables are read-model projections only; never bound as the `EventStore`.
- **R3 — projection/log divergence** (bad ordering or idempotency). *Mitigation:* persisted positions; idempotent append (INV-16); replay-equivalence gate (ADR-001 §8).
- **R4 — non-deterministic replay** if recorded values are recomputed. *Mitigation:* the determinism seam already records timestamps/ids as event data (INV-17); asserted by replay-equivalence with deterministic factories.
- **R5 — partial batch on crash mid-commit.** *Mitigation:* one durable transaction per commit; atomicity test.
- **R6 — INV-07 dual-representation debt persists.** *Mitigation:* time-boxed, declared coexistence window with a converge-then-delete exit.

## 8. Migration Impact

- **Direction:** v2 event log authoritative (terminal); v1 remains system-of-record during coexistence; convergence via the outbox seam. No big-bang rewrite.
- **Order within P1:** durable event store → durable projections/snapshots → durable repositories/UoW; each flag-gated, each proven against the in-memory oracle.
- **v1 retirement** of `memory/*` and outbox is deferred to P10, only after the corresponding v2 seam is default-on and stable (converge-then-delete).
- **Releasability:** the repository remains releasable at every step; default stays in-memory until parity, and rollback is a flag flip.

## 9. Validation

Ratifies the *direction*; the following are the entry gate for defaulting the durable store on (P1), mirroring ADR-001's forward-looking Validation Strategy:

- **Interface parity:** the synchronous `sqlite3` `EventStore` passes the existing `InMemoryEventStore` suite unchanged.
- **Replay equivalence (ADR-001 §8):** durable write → process restart → `read_all` → rebuild → byte-identical projection.
- **Position durability:** `global_sequence`/`stream_position` are stable across restart (never reassigned).
- **Serialization round-trip:** `VersionedSerializer` envelope → `sqlite3` → back is identity-preserving; `content_hash` stable; upcasting exercised.
- **Idempotent append across restart (INV-16):** re-append after reload is a no-op; duplicate id / different content raises.
- **Commit atomicity:** simulated crash mid-commit lands nothing.
- **Guardrail:** `async def` count in `nexus_*` remains 0.

## 10. Future Evolution

- Distributed / partitioned log (partition by correlation id) and cold-storage tiering fit unchanged — nothing here assumes a single-node store beyond an ordered, durable, append-only log (ADR-001 §10).
- Snapshot compaction and replay-window truncation attach as operational policy without changing authority.
- An alternative durable driver (e.g. a server database) can replace `sqlite3` behind the same synchronous protocol without touching call sites, if scale ever demands it.

## 11. References

- `docs/v2/P0_ADR007_PERSISTENCE_SPIKE.md` (the evidence this ADR ratifies)
- `adr/ADR-001.md` §3, §4, §8, §9 (event authority; rejected alternatives; validation; migration)
- `docs/v2/IMPLEMENTATION_READINESS_REVIEW.md` (C1, H1, H2, INV-13 blocker)
- `docs/v2/CONSTITUTIONAL_MIGRATION_BLUEPRINT.md` (Stage 1; "outbox becomes the log")
- `docs/v2/CONSTITUTIONAL_ENGINEERING_PROGRAM.md` (P1)
- Invariants: INV-01, INV-07, INV-13, INV-14, INV-16, INV-17, INV-22
- Source: `nexus_core/persistence/interfaces.py`, `nexus_infra/{event_store,projections,snapshots,unit_of_work,serialization}.py`, `nexus/database.py`, `nexus/memory/*`
