# P0 Spike — ADR-007 Persistence Authority

**Type:** Technical spike (evidence only — no production code, no redesign, no commits)
**Purpose:** Eliminate the highest architectural implementation risk in the Readiness Review (H1 sync/async boundary, H2 authoritative-store model, INV-13/14) so ADR-007 can be written without further architectural research.
**Method:** Every claim below is verified from source (file:line) or from a ratified decision document. Findings are labelled **[FACT]** (verified in source), **[ASSUMPTION]** (reasoned, not proven), or **[RECOMMENDATION]**. Prior reports were **not** trusted; two independent source sweeps (v1 and v2) plus direct reads of the substrate were performed.

> **Headline:** The authority question is **already ratified** — `adr/ADR-001.md` §3 (Accepted, Phase 0) decides Nexus is event-sourced with the event log authoritative and state as a projection. v2's substrate honors this **in memory**; v1 is a CRUD/state-authoritative system with an audit side-log. ADR-007 is therefore **not** "choose CRUD vs event-sourcing" (settled) — it is "**how does the already-event-sourced, synchronous, in-memory v2 kernel become durable, given v1's async-SQLite CRUD store**." The evidence points to exactly one safe direction.

---

## 1. Executive Summary

**[FACT] The authority decision is not open — it is ratified.** `adr/ADR-001.md:47-49`: *"Nexus is event-sourced with materialized projections. The append-only Event Log is the single authoritative source of operational truth. Current State and Checkpoints are derived artifacts, never independent sources of truth."* ADR-001 §4.A **explicitly rejected** "Pure state-based (CRUD) with an event side-channel" — which is precisely what v1 is. So **Option A (v1 database authoritative) is already a rejected alternative**, not a live candidate.

**[FACT] v2 already implements the event-sourcing seam correctly — but only in memory.** The `EventStore` Protocol is authoritative and append-only (`nexus_core/persistence/interfaces.py:50-51`); the concrete store is `InMemoryEventStore` backed by a Python `list` (`nexus_infra/event_store.py:53,57`); state is a deterministic fold via `ProjectionEngine.rebuild()` (`nexus_infra/projections.py:81-86`); replay determinism is enforced by recording non-deterministic values as event data (`nexus_core/domain/event.py:33,41`) with an injectable `TimestampSource`/`IdentifierFactory`. **Zero `async def` exist in any `nexus_*` package.** No durable event store, serializer-to-medium, or SQL exists in v2.

**[FACT] v1 is CRUD-authoritative with an audit side-log.** Entity state is a single mutable column UPDATEd in place, with the event logged *afterward* as a side effect (`nexus/memory/task_service.py:130` mutate `task.status` → `:158` `log_event`). There is **no `Repository` class and no `UnitOfWork` class** (grep: no matches); services own `AsyncSession` directly. The backing DB is **SQLite** accessed via **async `aiosqlite`** (`nexus/database.py:22-28,100-106`). Event replay exists but rebuilds only the conversational `ContextFrame`, never entity truth (`nexus/memory/manager.py:1-5,61-101`).

**[RECOMMENDATION — one direction] Adopt Option B (v2 durable event store authoritative) as the terminal architecture, reached through a bounded transitional Hybrid.** Implement a **synchronous** durable `EventStore` behind the *existing sync Protocol* using the standard-library `sqlite3` driver — **not** by reusing v1's async engine and **not** by introducing async into v2. This resolves H1 (there is no sync/async boundary inside v2 because v2 stays fully synchronous; the async lives only in the legacy v1 process during coexistence) and H2 (the event log is authoritative per ADR-001; v1's mutable tables are demoted to projections via the seam ADR-001 §9 already names: *"the outbox becomes the log"*). INV-13/14 are never at risk because v1's mutable store is **never elevated to authoritative under the v2 platform**; the two authorities remain separate until v2's durable log takes over.

**[FACT] A documentation hazard ADR-007 must resolve:** the label "ADR-007" collides. In `blueprint/DECISIONS/` **`ADR-007-email-provider.md` already exists**; the v2 constitutional series `adr/ADR-001..004.md` stops at 004; there is **no persistence ADR file in either series**. "ADR-007" is a *logical* name from the Readiness Review, not a filed document. ADR-007 must choose a non-colliding home (recommended: the v2 `adr/` series, next free number).

**[FACT] A tension between two authoritative documents must be reconciled (and this spike reconciles it):**
- `adr/ADR-001.md:47-49,180-187` → event log authoritative; relational tables demoted to projections; migrate via dual-write then flip.
- `CONSTITUTIONAL_MIGRATION_BLUEPRINT.md:198,235,304` (Stage 1 / "ADR-007") → *"bind v2 repos → v1 durable store… no behavior change… v1 and v2 now share truth,"* reusing v1's SQLAlchemy store.
- `IMPLEMENTATION_READINESS_REVIEW.md:210` → binding v1's mutable CRUD store under v2 **violates INV-13; "a blocker, not a bounded exception."**

Reconciliation (below, §4/§8): the Blueprint's "bind v2 repos to v1 store" is safe **only** because a v2 `Repository` is a *projection/read-model* (`interfaces.py:36`), never the write authority. The write authority is the `EventStore`, which must be backed by its **own durable log**, not v1's mutable rows. The Blueprint's "share truth / no behavior change" phrasing is the dangerous part and ADR-007 must replace it with "share **data** during migration; the event log is the sole write authority."

---

## 2. Current v1 Persistence  *(all [FACT], source-verified)*

**Backing store & driver.** SQLite via async SQLAlchemy 2.x — `create_async_engine`, `AsyncSession`, `async_sessionmaker`, `AsyncAttrs` (`nexus/database.py:22-28`); SQLite WAL + `foreign_keys=ON` + `busy_timeout` pragmas (`nexus/database.py:100-106`). Backing DB is SQLite (`sqlalchemy.dialects.sqlite.JSON` in models).

**Schema encodes the truth model.** Two mixins (`nexus/database.py:54-92`): `TimestampMixin` (`id, created_at, updated_at[onupdate], is_archived`) for **mutable** tables; `AuditMixin` (`id, created_at` only) for **append-only** tables — docstring: *"Mixin for immutable, append-only tables."* Mutable tables include `tasks, approvals, executions, system_policies, …`; append-only tables are only `audit_log, system_events, system_metrics_raw` (`nexus/memory/models.py:1-6,184-199`).

**No Repository, no UnitOfWork.** Grep for `class \w*Repository` and `UnitOfWork` → no matches. Persistence is via **Service classes holding an `AsyncSession`** (`MemoryService` `service.py:26`; `TaskService` `task_service.py:41`; `ApprovalService` `approvals/service.py:22`; `PolicyService` `policy_service.py:25`). The de-facto transaction boundary is the `get_session()` async context manager — commit on clean exit, rollback on exception (`nexus/database.py:152-192`). Services `flush()`, the outer block commits.

**Truth = mutable rows; events are a secondary ledger.** State is a single mutable column UPDATEd in place, event logged *after*: `task.status = new_status.value` (`task_service.py:130`) → flush → `memory_service.log_event(...)` (`:158`) → publish (`:162`). Reads for decisions query the mutable row, never replay: `check_approval_gate` selects current `ApprovalRecord.status == APPROVED` (`approvals/service.py:243-255`); `PolicyService.get_policy` reads the current `SystemPolicyRecord` (`policy_service.py:59-72`). `NexusEvent` is a frozen envelope (`nexus/core/events.py:18-49`) written to append-only `audit_log` (`service.py:33-54`) — but it records *of* changes; it is not the system of record.

**Event replay exists — but only for session context.** `ContextCompiler` loads the latest checkpoint then folds newer `audit_log` records into a `ContextFrame` (messages/model/tools) — *"derived state traversal"* (`nexus/memory/manager.py:1-5,61-101`). It does **not** govern task/approval/execution status.

**Transactional outbox — the migration seam.** `MemoryService.log_event` writes the audit record **and** a `system_events` outbox row in the *same transaction* before flush (`service.py:33-69`); `gateway/outbox.py:171-212` sweeps and marks sent. A second, richer outbox (`communication_outbox.py:85-352`) adds lease/retry/backoff/dead-letter over `system_outbox`. **This is exactly the seam ADR-001 §9 names: "outbox becomes the log."**

**Policy is the nearest to dual-authority.** `system_policies` (mutable current) + `system_policy_history` (immutable) with optimistic-locked in-place UPDATE + history insert + audit (`policy_service.py:97-172`); fails closed on missing key or DB error (`:54-95`). Even so, evaluation reads the **mutable** current row.

**Migrations.** Alembic present at repo root, 5 versions (`alembic/versions/`), but runtime bootstrap uses `Base.metadata.create_all` (`nexus/api.py:122-125`), **not** migrations.

**Scheduler.** APScheduler `AsyncIOScheduler`, **no DB jobstore** — jobs are in-memory; only job *runs* are audited (`nexus/scheduling/scheduler.py:39-108`, `jobs.py:27-90`).

**v1 truth verdict:** State-oriented CRUD with an audit trail, a transactional outbox, and a localized event-replay read-model for chat context. **Not** event-sourced. It is ADR-001's rejected Alternative A.

---

## 3. Current v2 Persistence  *(all [FACT], source-verified)*

**Authority is declared and wired.** `EventStore` Protocol: *"The authoritative append-only log (ADR-001). Append and read only — never update"* (`nexus_core/persistence/interfaces.py:50-51`). Composition root's single write path: `emit()` appends to the store **then** publishes — *"emit is the only way a fact becomes true"* (`nexus_infra/composition.py:10-12,65-68`). Repositories are *"a CRUD-free read model"* (`interfaces.py:36`); state is *"a projection (ADR-001)"* (`interfaces.py:61-62`).

**All six persistence Protocols are synchronous** (`interfaces.py`): `Serializer` (22), `Repository[T]` (35), `EventStore` (50), `Projection[S]` (61), `Snapshot[S]` (75), `UnitOfWork` (88) — every method `def`, none `async`. Module docstring: *"Nothing here opens a connection, chooses a format, or touches storage."*

**Every concrete impl is in-memory.** `InMemoryEventStore` (`event_store.py:53`, backed by `list`+`dict`), `InMemoryRepository[T]` + 5 domain repos (`repositories.py:30,117-149`), `InMemoryUnitOfWork` (`unit_of_work.py:40`), `InProcessEventBus` (`event_bus.py:64`), `InMemorySnapshotStore` (`snapshots.py:55`). `build_infrastructure` wires exactly these (`composition.py:85-108`).

**Event store mechanics are complete (just volatile).** Store-assigned, authoritative positions: `StoredEvent.global_sequence` (1-based) + `stream_position` (0-based) *"assigned by the store, never by the caller, so ordering is authoritative and deterministic"* (`event_store.py:38-51`). Idempotent append by `identifier` (INV-16), duplicate-different-content → `DuplicateEventError` (`:93-104`); optimistic concurrency via expected version (`:86-118`); snapshot-plus-replay tail via `read_from` (`:140-148`).

**UnitOfWork already models a SQL-shaped transaction.** Events staged via `collect`, flushed atomically on `commit` after a pre-validation that *"raises before any side effect"* so *"a commit never lands a partial batch"* (`unit_of_work.py:8-13,91-106`); rollback restores repo snapshots (`:108-116`). Docstring: *"the same contract would hold over a SQL transaction"* (`:6-7`).

**Replay determinism is enforced by design (INV-17).** `Event.timestamp` is *"captured as data so replay is deterministic"* and `payload` holds *"non-deterministic values captured as recorded data"* (`event.py:33,41`). The wall clock is observability-only and *"never written into the authoritative event payloads"* (`nexus_infra/clock.py:1-7`). Concrete replay: `nexus_workflows/executor.py:61 reconstruct()` rebuilds from `event_store.read_all()` — *"the same event store always yields the same replayed timeline… a byte-identical event stream"* (`executor.py:5,101-103`).

**Serialization substrate exists but is unwired to any medium.** `VersionedSerializer` implements `Serializer` with a `{schema_version,type,data}` envelope (`serialization.py:59-83`); `canonical_json`/`content_hash` give a deterministic byte image (used only for in-memory snapshot integrity, `snapshots.py:83,118`). Explicit gap: *"No transport protocol is introduced — this is structural (de)serialization only"* (`serialization.py:14`). **Nothing writes serialized events to disk/SQL.**

**No durability anywhere.** No `sqlalchemy/sqlite3/aiosqlite/psycopg/pickle` imports in `nexus_*` source; **0 `async def`** across all 20 packages; the only `open(`/file writes are repo-analysis utilities in `nexus_workflows` (`repo_profile.py`, `a1.py:68`), unrelated to domain persistence. Durability is repeatedly marked "Phase-2" (`event_store.py:16-17`, `unit_of_work.py:6-7`).

**v2 truth verdict:** A correctly-shaped, authoritative-log event-sourcing kernel with full replay/idempotency/snapshot semantics — **entirely in memory**. Truth is authoritative but volatile; the durability half (persistent `EventStore` + `Serializer`→medium) is deferred.

---

## 4. Architectural Comparison

Four candidate directions, scored on nine axes. **A = v1 DB authoritative; B = v2 event store authoritative (durable); C = Hybrid (transitional coexistence); D = alternative discovered from evidence.**

### Option A — v1 database remains authoritative
| Axis | Assessment |
|---|---|
| Architecture | **Reverses ratified ADR-001 §3.** v1 is the rejected Alternative A (`ADR-001.md:92-97`). |
| Invariant compatibility | **Violates INV-13/14** (mutable CRUD rows become truth under an event-sourced platform). Readiness `:210` calls this a hard blocker. |
| Migration complexity | Low short-term (nothing moves) — but it is not migration, it is abandonment of v2's model. |
| Replay correctness | **Broken** — v1 entity state is not reconstructable from events (replay is chat-context only, `manager.py`). |
| Operational complexity | Low (status quo). |
| Performance | Good reads (direct rows). |
| Testing complexity | Low, but cannot test replay-equivalence (there is nothing to replay). |
| Rollback | N/A. |
| Long-term maintainability | **Dead end** — forecloses every "Nexus thinks" capability that depends on durable event history. |
**Verdict: Rejected — constitutionally and by INV-13/14.**

### Option B — v2 durable event store becomes authoritative *(terminal target)*
| Axis | Assessment |
|---|---|
| Architecture | **Aligns with ratified ADR-001.** Only the durability half is added; the seam already exists. |
| Invariant compatibility | Satisfies INV-13/14 (log authoritative, state projection) and INV-17 (recording seam already built). |
| Migration complexity | Medium — requires a durable store + serializer-to-medium + projection rebuild-on-boot; but no v2 call-site changes (Protocol unchanged). |
| Replay correctness | **Already proven in-memory** (`projections.py:81`, `executor.py:61`); extends to durable via a round-trip test. |
| Operational complexity | Medium (rebuild, snapshot cadence, event upcasting) — ADR-001 §5 accepts this cost. |
| Performance | Reads via materialized projections (fast); append is an ordered insert. |
| Testing complexity | Medium — interface-parity (reuse in-memory suite) + durability round-trip + replay-equivalence. |
| Rollback | Clean — durable store is flag-gated; default remains `InMemoryEventStore` until proven. |
| Long-term maintainability | **Best** — one source of truth, native audit/replay/knowledge. |
**Verdict: Recommended terminal state.**

### Option C — Hybrid (v1 system-of-record + v2 event store, during coexistence) *(transitional path to B)*
| Axis | Assessment |
|---|---|
| Architecture | Correct **as a migration phase only**, not an end state. v1 stays authoritative *for v1*; v2 event store authoritative *for v2*; the two are not merged. |
| Invariant compatibility | Safe **iff** v1's mutable store is never bound as the authority under v2. INV-07 dual-representation is a *declared, bounded, temporary* exception (Readiness `:212`). |
| Migration complexity | Highest transient complexity (two stores, shadow, dual-write, reconciliation) — but lowest *risk* (Readiness `:129,239`). |
| Replay correctness | v2 replay correct on its own log; v1 unaffected. |
| Operational complexity | High during coexistence (two systems, diff dashboards). |
| Performance | Shadow adds write amplification during the window only. |
| Testing complexity | High — dual-read diff + replay-equivalence + shadow-equivalence gates. |
| Rollback | Best — flip a flag, v1 is untouched (`ADR-001.md:184-187` incremental path). |
| Long-term maintainability | Not an end state — must converge to B and delete duplicates, or INV-07 debt persists. |
**Verdict: Adopt as the transitional mechanism that delivers B safely.**

### Option D — Alternative discovered from evidence: **sync durable store, no async bridge, "outbox becomes the log"**
This is not a fourth authority model — it is the **implementation discovery** that makes B/C safe and collapses H1:
- **[FACT]** v1's DB is **SQLite** (`database.py:100-106`). Python's standard library ships a **synchronous** `sqlite3` driver.
- **[RECOMMENDATION]** Implement the durable `EventStore` with **sync `sqlite3`** behind the existing sync Protocol. v2 stays 100% synchronous end-to-end; **there is no async→sync boundary inside v2 at all.** The async persistence stays confined to the legacy v1 process during coexistence.
- **[FACT]** ADR-001 §9 already prescribes the data seam: *"the outbox is a natural seam: v2 promotes the event log to authoritative and demotes relational tables to projections… the v1→v2 path is 'outbox becomes the log.'"* v1's transactional outbox (`service.py:33-69`) already emits events in-transaction.
**Verdict: This is the recommended *how*. It removes the single hardest risk (async bridge) instead of managing it.**

---

## 5. Hidden Decisions ADR-007 Must Settle  *(each evidence-anchored)*

1. **Authoritative store model (H2).** *Evidence:* `ADR-001.md:47-49` (settled: event log) vs Blueprint `:304` ("share truth"). *Decision:* affirm event log authoritative; v1 tables → projections. **Mostly pre-decided by ADR-001; ADR-007 must restate and bind it against the Blueprint phrasing.**
2. **Sync/async boundary (H1).** *Evidence:* `interfaces.py` all sync vs `nexus/database.py:22-28` async. *Decision:* keep v2 sync; durable store uses sync `sqlite3`; **no async bridge**; async remains in v1 only.
3. **Position authority on reload.** *Evidence:* `event_store.py:38-51` positions assigned by store. *Decision:* persist assigned `global_sequence`/`stream_position`; never recompute on load (order must survive restart).
4. **Transaction boundary mapping.** *Evidence:* `unit_of_work.py:8-13,91-106` staged-then-atomic-flush. *Decision:* how `commit` maps to one durable transaction (append batch + projection update atomically; partial-batch already prevented).
5. **Projection persistence vs rebuild-on-boot.** *Evidence:* repos are in-memory projections (`repositories.py:41`); `rebuild()` exists (`projections.py:81`). *Decision:* are projections persisted, or rebuilt from the log (± snapshot) at startup? (Consistency-model dependency.)
6. **Consistency model.** *Evidence:* ADR-001 §5 *"eventual consistency between the log and projections must be reasoned about explicitly."* *Decision:* same-transaction (synchronous) projection update vs eventual.
7. **Snapshot cadence & recovery.** *Evidence:* `snapshots.py` complete but *"Recovery behavior is a later phase"*; `read_from` tail-replay exists (`event_store.py:140`). *Decision:* snapshot cadence + rebuild-from-nearest-snapshot policy (INV-22: recover, never restart from Goal).
8. **Dual-write / migration seam.** *Evidence:* ADR-001 §9 "outbox becomes the log"; v1 outbox in-transaction (`service.py:33-69`). *Decision:* shadow-only → dual-write → flip reads → log authoritative → demote tables; which store answers reads at each step.
9. **Migration ordering & INV-07 exception window.** *Evidence:* Readiness `:212` (bounded dual-representation acceptable if declared). *Decision:* the explicit, time-boxed coexistence declaration and its converge-then-delete exit.
10. **Serialization wire format.** *Evidence:* `serialization.py:14` format *"deferred"*; `canonical_json` available. *Decision:* concrete durable format (recommended: canonical JSON in `sqlite3`) + upcasting on read (`event.py:31`).
11. **Failure recovery on restart.** *Evidence:* `read_from` + snapshot restore exist but unwired to a durable medium. *Decision:* boot sequence = load snapshot → replay tail → serve.
12. **ADR numbering / document home.** *Evidence:* `blueprint/DECISIONS/ADR-007-email-provider.md` exists; `adr/` stops at 004; no persistence ADR filed. *Decision:* file the persistence ADR in the `adr/` series at the next free number (and treat "ADR-007" as its logical alias).

*(No invented decisions — every item cites source. Snapshot/recovery *behavior* beyond durability is out of ADR-007 scope and belongs to the Recovery phase.)*

---

## 6. Spike Experiments — sufficiency assessment

The prompt's example spikes are assessed for sufficiency; two are **misdirected as written** and four experiments are **added**. All are proposed as throwaway spikes against copies/new modules — **no production code changes.**

| # | Proposed spike | Sufficient? | Assessment / correction |
|---|---|---|---|
| 1 | Can v2 `Repository` protocol wrap `AsyncSession`? | **Misdirected** | This tests the *rejected* async-bridge path, and conflates Repository (a projection) with the EventStore (the authority). Replace with **Spike 1′:** a sync `sqlite3`-backed `EventStore` passes the **existing `InMemoryEventStore` test suite unchanged** (interface parity). Run the original only as a **negative** spike to *document* the async-bridge hazard. |
| 2 | Can synchronous engines safely consume async persistence? | **Sufficient as a risk probe** | Answer from evidence: only via an async→sync bridge with deadlock risk (R1). The recommendation **avoids** this by using a sync driver; run it to confirm the hazard, not to adopt the path. |
| 3 | Can event replay reconstruct every projection? | **Sufficient with extension** | Already proven in-memory (`projections.py:81`, `executor.py:61`). Extend to **durable round-trip**: write → process restart → `read_all` → `rebuild` → byte-identical projection (reuse ADR-001 §8 replay-equivalence test). |
| 4 | Can v1 coexist during migration? | **Sufficient** | Prove the dual-process + outbox-seam + shadow model: v1 keeps serving; v2 durable store ingests via the outbox; diff v1-state vs v2-projection. |
| 5 | Can projections replace CRUD ownership? | **Sufficient** | Map each v1 mutable table (`tasks`, `approvals`, `system_policies`) to a v2 projection folded from events; prove the projection reproduces the mutable row losslessly. |
| 6 | *(added)* Position durability | **Required** | Prove `global_sequence`/`stream_position` persist and are **not** reassigned across restart (`event_store.py:44-45`). |
| 7 | *(added)* Serialization durability round-trip | **Required** | `VersionedSerializer` envelope → `sqlite3` → back is identity-preserving; `content_hash` stable; upcasting path exercised (`serialization.py`, `event.py:31`). |
| 8 | *(added)* Idempotent append across restart (INV-16) | **Required** | Re-append after reload is a no-op; duplicate id / different content raises `DuplicateEventError` durably. |
| 9 | *(added)* Transactional commit atomicity over durable store | **Required** | UoW `commit` maps to one durable transaction; simulated crash mid-commit lands **nothing** (extends `unit_of_work.py:8-13`). |

**Sufficiency conclusion:** Spikes 1′, 3(extended), 4, 5, 6, 7, 8, 9 together are **sufficient** to write ADR-007. Spikes 1(original) and 2 are retained only to *document why the async bridge is rejected*.

---

## 7. Risks

| ID | Risk | Sev | Evidence | Mitigation |
|---|---|---|---|---|
| R1 | Async→sync bridge deadlocks if v1's async engine is wrapped under the sync Protocol | **High** | `interfaces.py` sync vs `database.py:22-28` async | **Eliminate, not manage:** use sync `sqlite3`; keep v2 fully synchronous (Option D). |
| R2 | v1 mutable store bound as authority under v2 → INV-13 violation | **High (blocker)** | Readiness `:210`; Blueprint `:304` phrasing | Event log is sole write authority; v1 store is projection/source only; never bound as EventStore. |
| R3 | Projection/log divergence (bad idempotency or ordering) | Med | ADR-001 §7 R-01 | Persist store positions (Spike 6); idempotent append (Spike 8); replay-equivalence gate (Spike 3). |
| R4 | Non-deterministic replay if recorded values are recomputed | Med | ADR-001 §7; `event.py:33,41` | Seam already recording-not-recomputing; assert with replay-equivalence + `DeterministicIdentifierFactory`. |
| R5 | Crash mid-commit lands a partial batch durably | Med | `unit_of_work.py:8-13` (prevented in-memory) | One durable transaction per commit (Spike 9). |
| R6 | INV-07 dual-representation debt persists (coexistence never ends) | Med | Readiness `:212` | Declare a time-boxed window; converge-then-delete exit gate (ADR-001 §9). |
| R7 | ADR filed under a colliding number / wrong series | Low | `blueprint/DECISIONS/ADR-007-email-provider.md`; `adr/` ends at 004 | File in `adr/` at next free number; alias "ADR-007". |
| R8 | Serialization format churn breaks old replays | Low | `serialization.py:14` deferred; `event.py:31` upcasting | Freeze canonical-JSON format + append-only, backward-compatible event schemas + upcasting. |

---

## 8. Recommended Direction  *(exactly one)*

**Adopt Option B (v2 durable event store is the single authoritative source of truth), implemented as Option D (a synchronous `sqlite3`-backed `EventStore` behind the existing sync Protocol, no async bridge), and reached via Option C (a bounded, shadow-first coexistence where v1's transactional outbox is the migration seam — "outbox becomes the log").**

Concretely:
1. **Authority:** the event log is authoritative; current state is a materialized projection; checkpoints are snapshots at a log position. *(Restates ratified ADR-001 §3 — ADR-007 binds it against the Blueprint's "share truth" phrasing, replacing it with "share **data** during migration; the log is the sole write authority.")*
2. **Durability:** a synchronous durable `EventStore` using standard-library `sqlite3`, plus `VersionedSerializer` wired to canonical-JSON-in-SQLite, behind the **unchanged** sync Protocol (`interfaces.py`). No v2 call-site changes. No `async def` enters `nexus_*`.
3. **Migration:** shadow-only → dual-write via the v1 outbox → flip reads to v2 projections → make the v2 log authoritative → demote v1 relational tables to projections → converge-then-delete. Flag-gated at every step; default remains `InMemoryEventStore` until parity is proven.

**Why not the others:**
- **Option A (v1 authoritative): rejected** — it is ADR-001's already-rejected Alternative A and violates INV-13/14 (Readiness `:210`). Choosing it abandons v2's ratified model and every durable-history capability.
- **Naive Blueprint Stage-1 ("bind v2 repos to v1 store, share truth, no behavior change"): rejected as written** — if it elevates v1's mutable store to authority under v2, it is the INV-13 blocker. It is salvageable only re-read as "v2 `Repository` = read-only projection over v1 data during migration, EventStore backed by its own durable log" — which is Option C.
- **Async bridge (wrap `AsyncSession` under the sync Protocol): rejected** — unnecessary given sync `sqlite3`, and carries deadlock risk (R1). Managing a hazard you can delete is the wrong trade.
- **Make v2 async: rejected** — 0 `async def` across 26.7k LOC; the blast radius is the entire synchronous spine, for no benefit (the store is local SQLite, not a network DB).
- **Pure event sourcing with no stored projection: rejected** — already rejected by ADR-001 §4.B (hot-path guard cost); v2 correctly materializes projections.

---

## 9. Questions ADR-007 Must Answer

1. Does ADR-007 **restate and bind** ADR-001's event-log authority, explicitly demoting v1 relational tables to projections, and explicitly retract the Blueprint's "share truth / no behavior change" phrasing? *(H2, R2)*
2. What is the **durable EventStore driver**, and does it keep v2 fully synchronous? *(Recommended: sync `sqlite3`.)* *(H1, R1)*
3. How are **store-assigned positions** (`global_sequence`, `stream_position`) persisted and guaranteed stable across restart? *(H3)*
4. How does `UnitOfWork.commit` map to **one durable transaction**, and what guarantees no partial batch lands? *(H4, R5)*
5. Are **projections persisted or rebuilt on boot** (from log ± snapshot), and what is the **consistency model** (same-transaction vs eventual)? *(H5, H6)*
6. What is the **snapshot cadence** and the restart/recovery sequence (nearest snapshot → replay tail)? *(H7, H11)*
7. What is the **migration ordering** (shadow → dual-write → flip reads → log-authoritative → demote → delete), and which store answers reads at each step? *(H8)*
8. What is the **declared, time-boxed INV-07 coexistence exception** and its converge-then-delete exit gate? *(H9, R6)*
9. What is the frozen **durable serialization format** and the **event-upcasting** rule for old events? *(H10, R8)*
10. Under what **ADR number and in which series** is this decision filed, given the `ADR-007-email-provider` collision and the `adr/` series ending at 004? *(H12, R7)*

---

## 10. Exit Criteria for Approving ADR-007

ADR-007 may be marked **Accepted** only when **all** of the following hold:

1. **All ten questions in §9 are answered** in the ADR text, each with a single decision (no "Unresolved" section).
2. **A spike report is attached** demonstrating the required experiments pass: **Spike 1′** (sync `sqlite3` EventStore passes the existing `InMemoryEventStore` suite unchanged), **Spike 3-extended** (durable write → restart → rebuild → byte-identical projection, per ADR-001 §8 replay-equivalence), **Spike 6** (positions stable across restart), **Spike 7** (serialization round-trip identity + stable hash), **Spike 8** (idempotent append across restart), **Spike 9** (commit atomicity — no partial batch on simulated crash).
3. **INV-13/14 are provably upheld:** the ADR states, and the spike shows, that the event log is the sole write authority and v1's mutable store is never bound as the EventStore.
4. **INV-17 is provably upheld:** replay reproduces byte-identical state using recorded (not recomputed) timestamps/ids (`DeterministicIdentifierFactory` + `FixedTimestampSource`).
5. **H1 is closed with zero async in `nexus_*`:** the recommended durable store keeps `async def` count at 0 across all `nexus_*` packages (guardrail-checked).
6. **The migration path is releasable at every step:** each stage is flag-gated, default-safe, and reversible (default remains `InMemoryEventStore` until parity is proven), with a declared, time-boxed INV-07 coexistence exception and a converge-then-delete exit.
7. **The document-home question is resolved:** filed in the `adr/` series at a non-colliding number, superseding/aliasing the logical "ADR-007" label.
8. **Sign-off** from the Architecture Review Board (the deciders of record for `adr/ADR-001.md`).

---

### Fact / Assumption / Recommendation ledger (summary)
- **[FACT]** ADR-001 ratified event-log authority; v1 is rejected Alternative A; v2 substrate is sync + in-memory + replay-correct; v1 is async-SQLite CRUD with an audit side-log and an in-transaction outbox; positions/serializer/snapshot substrate exist but are unwired to a medium; `async def` in `nexus_*` = 0; ADR numbering collides.
- **[ASSUMPTION]** Standard-library `sqlite3` (sync) is an acceptable durable driver for a local single-node store (consistent with v1's SQLite choice); projection rebuild-on-boot cost is bounded by snapshotting (per ADR-001 §5/§7). These are to be *confirmed* by Spikes 1′/3/6.
- **[RECOMMENDATION]** Option B terminal, via Option D implementation (sync `sqlite3`, no async bridge), via Option C migration (shadow-first, outbox-as-seam). Reject A, the async bridge, v2-goes-async, and the naive Blueprint Stage-1 reading.

*This spike changed production code: none. Commits: none.*
