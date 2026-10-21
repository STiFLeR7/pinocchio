# Phase 2 — Infrastructure Layer: Implementation Decisions

**Status:** Implemented. **Scope:** the operational substrate (`nexus_infra/`).
**Authority:** This document records *implementation decisions* only. It does not
amend any ADR, contract, or invariant — the architecture remains frozen. Where an
implementation suggested a possible future architecture change, it is recorded in
§5 as an observation with a recommendation, not applied.

Phase 2 turns the Phase 1 interfaces (`nexus_core.events`, `nexus_core.persistence`)
into working infrastructure: an event store, event bus, projection engine,
snapshot store, repositories, a unit of work, and their composition. It contains
no business logic.

---

## 1. Component → architecture mapping

| Component (`nexus_infra/…`) | Implements | ADR / AP | Invariants |
|---|---|---|---|
| `event_store.InMemoryEventStore` | `EventStore` | ADR-001, AP-201 | INV-13, INV-14 |
| `event_bus.InProcessEventBus` | `EventConsumer` | AP-201 | INV-16, INV-39 |
| `event_versioning.InMemoryUpcasterRegistry` | `UpcasterRegistry` | ADR-001 §6, AP-101 | INV-17 |
| `projections.ProjectionEngine` | drives `Projection` | ADR-001 §3.2, AP-203 | INV-14, INV-16 |
| `snapshots.InMemorySnapshotStore` | `Snapshot` basis | ADR-001 §3.3, AP-204 | INV-14, INV-18 |
| `repositories.*` | `Repository[T]` | ADR-001 | INV-13/14 |
| `unit_of_work.InMemoryUnitOfWork` | `UnitOfWork` | ADR-001 | INV-15 |
| `composition.InfrastructureContext` | `EventEmitter` (`emit`) | AP-201/202 | INV-13 |
| `serialization.VersionedSerializer` | `Serializer` | AP-101 | INV-07 |
| `identifiers.*` | `IdentifierFactory` | AP-202 | INV-16 |

## 2. Key implementation decisions

1. **Separate package `nexus_infra`.** `nexus_core` is the pure foundation; its
   README promises "no implementations". Infrastructure therefore lives in an
   additive sibling package that depends on `nexus_core` and never the reverse
   (dependency inversion preserved). No `nexus_core` source changed.

2. **Optimistic concurrency uses the existing `Event.sequence_position`.** The
   Phase 1 `EventStore.append(event)` Protocol takes only an event, with no
   `expected_version` parameter. The store interprets a non-`None`
   `sequence_position` as the *expected stream version* and rejects a mismatch
   with `ConcurrencyConflictError`; `None` means "append at end, no expectation".
   A richer `append_expecting(event, expected_version)` is provided for explicit
   callers. This honours ADR-001's "optimistic concurrency / causal ordering per
   correlation id" without changing the frozen interface.

3. **Stream = correlation id; ordering is a monotonic counter.** Global order is
   deterministic insertion order; per-correlation order is the causal stream
   (INV-39). No clock participates in ordering.

4. **Idempotent append + idempotent projection (INV-16).** Re-appending an
   identical event is a no-op; re-using an identifier for different content is a
   `DuplicateEventError`. The projection engine dedupes by `event.identifier`,
   providing the AP-202 mechanism once, centrally.

5. **Snapshots carry a log position and expire by position, never by clock.**
   Integrity is a SHA-256 content hash verified on restore; expiry is an optional
   log-sequence horizon. This keeps recovery deterministic (ADR-001 §3.6).

6. **Atomic unit-of-work commit.** Before appending anything, the whole staged
   event batch is validated for appendability (no duplicate identifier, consistent
   stream position). If validation fails, nothing is appended and repositories are
   rolled back via begin-time snapshots — a commit never lands a partial batch.

7. **Observability is injected and inert by default.** `NullObservability` is the
   default zero-overhead sink; `InMemoryObservability` is used in tests. Timings
   use an injected `Clock` and are never written into event payloads, so a real
   production clock does not violate INV-17.

8. **Composition is explicit DI, no globals.** `build_infrastructure(...)` wires
   defaults; every dependency is overridable and `InfrastructureContext` can be
   constructed directly. No module-level singletons or service locators.

## 3. What was deliberately NOT built (out of scope)

Event-bus networking/brokers (Kafka/Rabbit/Redis/NATS), durable databases, the
state-machine *engine* that drives transitions, checkpoint/recovery *behaviour*,
event-schema *migration* logic (only the upcaster framework), distributed
locking, planning, context engineering, skills, orchestration, runtime/AI
execution, scheduling, and APIs. The substrate provides the primitives those
phases consume.

## 4. Validation gate (all met)

| Gate criterion | Result |
|---|---|
| Event replay works | ✅ replay-equivalence tests (engine rebuild from log == live state) |
| Projection rebuild works | ✅ `ProjectionEngine.rebuild` re-folds deterministically |
| Snapshot restore works | ✅ restore + integrity + expiry tests |
| Repository implementations pass | ✅ 5 concrete repos, immutability + OCC |
| Transactions pass | ✅ commit/rollback/atomic-flush/context-manager |
| Event ordering preserved | ✅ global + per-correlation ordering tests |
| Optimistic concurrency validated | ✅ store + repository conflict tests |
| Version compatibility validated | ✅ upcaster chaining + non-convergence guard |
| All Phase 1 tests still pass | ✅ 193 `nexus_core` tests unchanged |
| No architectural invariant violated | ✅ no ADR/contract/`nexus_core` change |

Coverage: `nexus_infra` ~98% (branch), ≥95% floor. Full suite: 373 tests,
`mypy --strict` clean, `ruff` clean.

## 5. Design observations (for future architectural review — NOT applied)

Per the Phase 2 mandate, better designs are documented and recommended, not
silently implemented. Two observations surfaced:

- **O-1 — The `EventStore` Protocol does not surface concurrency/replay
  positions.** Phase 1's `EventStore` exposes `append`, `read_stream`,
  `read_all`, but no `expected_version`, `stream_version`, or
  `read_from(position)`. ADR-001 *requires* optimistic concurrency and
  snapshot-plus-tail replay, so these capabilities exist on the concrete store as
  additional methods (and concurrency is threaded through `Event.sequence_position`).
  *Recommendation:* a future **ADR-001 amendment / Phase-1 interface enrichment**
  could promote `append_expecting`, `stream_version`, and `read_from` to the
  `EventStore` Protocol so higher layers depend on them abstractly. Low urgency —
  the current approach is contract-compatible.

- **O-2 — `EventEmitter.emit` semantics span store + bus.** "Emit = make a fact
  true" is realized in `InfrastructureContext.emit` (append to log, then publish),
  because neither the store nor the bus alone owns both responsibilities. This is
  correct and intentional; recorded so future readers know the emitter lives in
  composition, not in a single component. *Recommendation:* none — keep as is.

Neither observation blocks Phase 2 or requires action now; both are candidates
for the ADR backlog if/when a later phase needs the enriched interface.
