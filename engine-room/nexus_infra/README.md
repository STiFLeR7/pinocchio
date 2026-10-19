# `nexus_infra` — Nexus v2 Infrastructure Layer (Phase 2)

Concrete, generic implementations of the Phase 1 foundation interfaces
(`nexus_core.events` / `nexus_core.persistence`). This is the **operational
substrate**: where, how, and in what order operational state is stored,
transported, projected, and restored.

> If `nexus_core` defines *what the platform's primitives mean*, `nexus_infra`
> makes them *run*. It implements the frozen Protocols exactly; it never
> redefines them.

It contains **no** business logic — no planning, orchestration, skills, runtime
selection, AI execution, recovery behaviour, or APIs. Those are later phases that
*consume* this substrate without modifying it. The dependency direction is
one-way: `nexus_infra → nexus_core` (never the reverse).

---

## Layout (built in the mandated dependency order)

```
nexus_infra/
├── errors.py            Infrastructure error hierarchy (fail-fast, explainable)
├── clock.py             Clock protocol + System/Manual clocks (injectable timings)
├── observability.py     InfraEvent + Observability sink (Null / InMemory) + `timed`
├── serialization.py     VersionedSerializer + canonical_json + content_hash
├── identifiers.py       Uuid / Deterministic IdentifierFactory implementations
├── event_store.py       1 — append-only authoritative log (ordering, idempotency, OCC, replay)
├── event_bus.py         2 — in-process synchronous pub/sub with dead-lettering
├── event_versioning.py  upcaster registry (framework only)
├── projections.py       3 — projection engine (idempotent, deterministic fold, rebuild)
├── snapshots.py         4 — snapshot store (integrity, expiry, lineage, log position)
├── repositories.py      5 — identity-keyed repositories + the 5 concrete adapters
├── unit_of_work.py      6 — transactional boundary (atomic commit, snapshot rollback)
└── composition.py       7 — dependency-injection wiring (no globals, replaceable)
```

## What it guarantees (ADR-001, INV-13–18, INV-39)

- **Event-sourced.** The event store is the single authoritative, append-only log
  (INV-13). State is a projection; snapshots are derived and carry a log position
  (INV-14).
- **Deterministic.** Ordering uses a monotonic counter, not a clock; folding the
  same event sequence always yields the same state. Every clock/uniqueness
  dependency is injected so tests and replay are 100% reproducible.
- **Idempotent (INV-16).** Re-appending an identical event is a no-op; the
  projection engine dedupes by event identifier, so duplicate/out-of-order
  delivery causes no duplicate state change.
- **Optimistic concurrency.** Appends and repository writes assert an expected
  version and raise `ConcurrencyConflictError`; no locking.
- **Atomic commit.** The unit of work validates a whole event batch for
  appendability *before* any side effect, so a commit never lands partially.

## Design decisions (implementation only — architecture unchanged)

These choices implement the frozen architecture; none changes an ADR, contract,
or invariant. See `docs/v2/PHASE_2_INFRASTRUCTURE.md` for the full record.

- **Separate package.** `nexus_infra` is additive and keeps `nexus_core` pure
  (its README promises "no implementations").
- **Optimistic concurrency via `Event.sequence_position`.** The Phase 1
  `EventStore.append` Protocol takes only an event; the store reads the event's
  existing `sequence_position` as the *expected stream version*, and exposes a
  richer `append_expecting(event, expected_version)` for explicit use.
- **Snapshot expiry by log position**, never a wall clock — to stay
  deterministic.
- **Observability timings are injected** and never feed projections, so a real
  production clock does not violate INV-17 (replay determinism).

## Using the substrate

```python
from nexus_infra import build_infrastructure
from nexus_core.domain.event import Event

infra = build_infrastructure()          # all parts injectable / replaceable

event = Event(identifier="evt-1", type="goal.created", version="1",
              timestamp="2026-01-01T00:00:00Z", producer="intent_resolution",
              correlation_identifier="cor-1", execution_identifier=None,
              payload={}, source="api")

infra.emit(event)                        # append to the authoritative log, then publish
infra.event_store.read_all()             # replay the whole log
with infra.unit_of_work() as uow:        # transactional boundary
    infra.goals.add(...)                 # staged repo write
    uow.collect(event)                   # staged event
    uow.commit()                         # atomic flush (append + publish)
```

## What is intentionally absent (later phases)

Event-bus networking/brokers, durable databases, the state-machine *engine* that
drives transitions, checkpoint/recovery *behaviour*, planning, orchestration,
runtime/AI execution, scheduling, and any API. Those build on these primitives
without redesigning them.

## Verification

```bash
.venv/Scripts/python.exe -m ruff check nexus_infra/ tests/unit/nexus_infra/
.venv/Scripts/python.exe -m mypy nexus_infra/
.venv/Scripts/python.exe -m pytest tests/unit/nexus_infra/ -q
# or the whole gate, both packages:
make check
```
