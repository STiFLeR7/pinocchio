# P1 Implementation Report — Durable Infrastructure Foundation

- **Date:** 2026-07-13
- **Program:** P1 (Durable Foundation) of the Constitutional Engineering Program
- **Governing decision:** ADR-007 (Persistence Authority)
- **Rule observed:** implementation only — no redesign, no protocol/contract/invariant/ADR edits, no engine changes, no commit.

---

## 1. Summary of Work

The in-memory persistence substrate now has durable, SQLite-backed siblings **behind the same frozen synchronous protocols**. No engine was touched; no public API changed; no engine can tell whether persistence is memory-backed or durable.

**New code — `nexus_infra/durable.py`** (one cohesive module):
- `DurableEventStore` — the authoritative append-only log, SQLite-backed, full public surface of `InMemoryEventStore` (protocol `append`/`read_stream`/`read_all` + `append_expecting`/`read_from`/`read_all_stored`/`stream_version`/`global_length`/`contains`).
- `DurableRepository[T]` + `DurableGoalRepository`/`DurablePlanRepository`/`DurableArtifactRepository`/`DurablePolicyRepository`/`DurableKnowledgeRepository` — identity-keyed projection stores.
- `DurableUnitOfWork` — transactional boundary mapping `commit` to one SQLite transaction.
- `DurableSnapshotStore` — integrity-stamped snapshots with log-position expiry and lineage.
- `connect(db_path)` — a synchronous connection wired for explicit transactions (WAL, autocommit + explicit `BEGIN`/`COMMIT`).
- `build_durable_infrastructure(db_path, ...)` — composition returning a standard `InfrastructureContext`.

**Changed — `nexus_infra/composition.py`** (dependency injection only): added an injected `unit_of_work_factory` field to `InfrastructureContext` (default = `InMemoryUnitOfWork`) and routed `unit_of_work()` through it, so a durable context returns a durable Unit of Work transparently. `build_infrastructure` is unchanged in behavior.

**Changed — `nexus_infra/__init__.py`**: additive exports of the durable classes and `build_durable_infrastructure`.

**Tests** — `tests/unit/nexus_infra/test_durable_{event_store,repositories,unit_of_work,snapshots}.py` and `tests/integration/test_durable_restart.py`.

---

## 2. Architectural Compliance (ADR-007, ADR-001, invariants)

| Requirement | Status | How |
|---|---|---|
| Event Log remains authoritative | ✅ | `DurableEventStore` is the source of truth; repositories are projections over it. |
| State remains a projection | ✅ | Durable repositories reconstruct value-equal objects from storage (ADR-001 §3.2). |
| Synchronous implementation | ✅ | Standard-library `sqlite3`; **0 `async def`** added (verified across `nexus_infra`/`nexus_core`). |
| No async bridge | ✅ | No event loop, no `asyncio`; v2 stays fully synchronous end to end (INV-01). |
| No CRUD authority | ✅ | Repositories never own truth; writes are projection updates; the log is the write authority. |
| VersionedSerializer as the on-disk format | ✅ | Events and objects stored as the serializer's JSON envelope; positions persisted, never recomputed. |
| One durable transaction per commit | ✅ | `DurableUnitOfWork.commit` validates → appends → `COMMIT`; a failed pre-validation appends nothing and leaves the transaction open for rollback (no partial batch). |
| Idempotency (INV-16) | ✅ | Content-hash column; re-appending an identical event is a no-op, in-session and across restart. |
| Determinism / replay (INV-14/17) | ✅ | Non-deterministic values already recorded as event data; replay from the durable log reproduces projections identically. |
| No protocol / contract / invariant / ADR change | ✅ | Only additive code + one DI field; frozen `interfaces.py` untouched. |
| No engine changed | ✅ | Planning/Runtime/Validation/Recovery/Reflection/Knowledge/Workflow untouched; 1922 v2 unit tests green. |

---

## 3. Validation Results

Run with `--noconftest` (the repo-root `conftest.py` imports the v1 app, which requires `discord`, absent in this environment — a pre-existing condition unrelated to P1; the v2 infra tests are plain pytest functions using `factories.py`).

| Suite | Result |
|---|---|
| Existing in-memory infra tests (unchanged) | **180 passed** |
| New durable + restart tests | **53 passed** |
| Combined infra + durable + restart | **233 passed** |
| Full v2 unit suite (all engine packages) | **1922 passed — no regressions** |
| Lint (`ruff`, repo `ruff.toml`) on new/changed files | **clean** |

Required demonstrations (all green):
- **Existing in-memory tests continue to pass** — 180/180, no in-memory code touched.
- **Durable implementations pass the same behavioral tests** — mirrored suites for store/repo/uow/snapshot (value-equality parity; see §4.1).
- **Replay reconstructs projections identically** — `test_replay_reconstructs_projection_after_restart`, `test_identical_input_gives_identical_replay`.
- **Restart preserves history** — `test_restart_preserves_history`, `test_unit_of_work_commit_survives_restart`.
- **Event ordering preserved** — `test_global_ordering_preserved_across_restart` (global + per-stream).
- **Snapshot behavior deterministic** — `test_snapshot_restore_plus_tail_equals_full_replay`; content-hash integrity + log-position expiry tested.
- **Identical input → identical replay** — `test_identical_input_gives_identical_replay`.

---

## 4. Deviations

Two are **expected physical characteristics of durability, not design changes**; one is a deliberate, ADR-aligned refinement. None alters a protocol, contract, invariant, or engine behavior.

### 4.1 Value-equality, not object identity (expected)
The in-memory adapters return the *same Python instance* on read; a durable adapter reconstructs a *value-equal* object across the serialization boundary. This is exactly what ADR-001 §3.2 means by "state is a projection of the log." Consequently the durable parity tests assert `==` where the in-memory suites assert `is` (repositories: `repo.get(id) == obj`; snapshots: `restore(id) == state`). Events and domain objects are frozen Pydantic models with value equality, so every *semantic* behavior maps 1:1. This is not a deviation from ADR-007 — object identity is not a term of the `Repository`/`Snapshot` protocols.

### 4.2 Bus publish after durable commit (deliberate refinement)
`InMemoryUnitOfWork` publishes each event to the bus *during* the commit loop; `DurableUnitOfWork` publishes *after* the SQLite `COMMIT`. This guarantees the bus never observes an uncommitted fact and is crash-safe (a fact becomes true only once durable) — and it is friendlier to ADR-008 shadow correctness. Observable outcome is unchanged: after `commit()` returns, the committed events have been appended and published, exactly as before. No engine depends on publish-before-commit ordering.

### 4.3 Snapshot state stored structurally (bounded)
`DurableSnapshotStore.restore` returns the state as its structural JSON image (e.g. a tuple round-trips to a list), since projection state types are a later-phase concern. `content_hash` is stable across the tuple↔list normalization, so integrity holds. No P1 consumer reads snapshots (Recovery is out of scope); typed rehydration binds when projections are wired in a later phase. This is documented, not silent.

**Composition annotations:** `InfrastructureContext`'s field annotations remain the concrete in-memory types; the durable impls are passed as protocol-compatible (with `# type: ignore` at the wiring points). Widening the annotations to the frozen protocols is deferred to avoid a type-check cascade across engines that read the richer store API; it is runtime-correct today.

---

## 5. New Risks

| Risk | Severity | Mitigation / note |
|---|---|---|
| Single shared SQLite connection, single-threaded | Low | v2 is fully synchronous (0 `async def`); documented ceiling in `durable.py`. A per-connection pool is only needed if v2 ever runs the substrate concurrently. |
| Nested/concurrent Unit of Work on one connection | Low | Not supported (SQLite single transaction per connection); v2 uses one UoW at a time. Would need savepoints if that changes. |
| Connection lifecycle not explicitly closed | Low | Closed on GC/process exit; a `close()`/context-manager on the context can be added when a process lifecycle owner exists (P3/P10). WAL sidecar files persist between runs by design. |
| Snapshot typed rehydration deferred | Low | No consumer yet; binds with projections in a later phase. |
| Durable path not yet flag-gated | Medium | By design: ADR-007 keeps in-memory the default; the durable store is opt-in via `build_durable_infrastructure`. The flag/shadow rollout is **P3** (ADR-008), not P1. |

No constitutional conflict was discovered. The one place evidence pressed against the letter of the task ("durable passes the *same* tests") is the identity-vs-equality point (§4.1); it is resolved by the protocols and ADR-001 (state is a projection), not by changing any design — reported here rather than silently adjusted.

---

## 6. Operational Implications

- **Storage:** one SQLite file per context (plus WAL/SHM sidecars). Schema is created idempotently on `connect` (`events`, `repository_objects`, `snapshots`).
- **Durability default:** unchanged — `build_infrastructure` (in-memory) remains the default; durable is explicit. This preserves ADR-007's "default-safe until parity proven" posture.
- **Recovery substrate:** restart rebuilds projections from the durable log (`ProjectionEngine.rebuild(store.read_all())`), optionally from the nearest snapshot + `read_from(pos+1)` — both demonstrated.
- **Observability:** the durable adapters emit the identical `InfraEvent`/counter set as the in-memory ones, so existing instrumentation works unchanged.

---

## 7. Performance Observations

- Per append: a small indexed `SELECT` (idempotency check), a `COUNT` (stream version), a `MAX(global_sequence)`, one `INSERT`, and a SHA-256 `content_hash` over the event's canonical JSON. All are O(1)/O(log n) against the PK and the `(stream, stream_position)` index.
- Reads (`read_all`/`read_stream`/`read_from`) are single indexed scans with per-row deserialization.
- No benchmark harness was built (out of P1 scope). Observed wall-clock: the full 233-test durable+in-memory suite runs in ~0.9s, and the 1922-test v2 suite in ~2s, on the durable path exercising real SQLite files. A dedicated append/rebuild budget (ADR-007 Performance Gate) is a P1-exit measurement scheduled with the flag rollout.

---

## 8. Remaining Work Before P2

P2 (Policy Engine) depends on the durable **log existing**, which it now does. It does **not** require the durable path to be default-on. Outstanding items, none blocking P2:

1. **Flag/shadow rollout (P3, ADR-008):** gate the durable store behind a feature flag and prove parity in shadow before defaulting on. P1 delivers the implementation; the safe cutover is P3.
2. **Performance Gate measurement:** append + projection-rebuild budget on a reference workload (ADR-007 §9), to be recorded at cutover.
3. **Connection lifecycle owner:** an explicit `close()`/lifecycle when a process owner exists (P3/P10).
4. **Snapshot typed rehydration:** binds when concrete projections are wired (later phase); not needed by any current consumer.
5. **Optional:** widen `InfrastructureContext` annotations to the frozen protocols for full static typing of durable wiring, and (optionally) parametrize the in-memory suites across both backends as a single shared oracle instead of mirrored suites.

**Verdict:** P1 is functionally complete against ADR-007. The durable substrate exists behind the frozen synchronous protocols, passes the behavioral contract by value-equality parity, preserves determinism and ordering across restart, and introduces no engine, protocol, or invariant change. No commit was made.
