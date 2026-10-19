# Scheduler Future Scaling (AP-103A requirement)

> Documentation only — no implementation. Extends the Scheduler Foundation design with the
> forward-looking scaling model required by AP-103A. v1.0.1 ships the **single-node** model only;
> everything below "Future" is design intent to keep the door open (constraint 6).

---

## 1. Scheduler Lease Model

A **lease** is the right to *fire* a given job at a given scheduled instant. It answers: "who runs
this job, and how do we prevent two runners from firing it at once?"

- **v1.0.1 (single node):** the lease is **implicit and trivial** — there is exactly one process, so
  the in-process `AsyncIOScheduler` is the sole authority. `max_instances=1` per job provides the
  *intra-node* lease (a job never overlaps itself). No cross-process lease is needed or implemented.
- **Idempotency as the safety net:** even without a formal distributed lease, every job is
  idempotent (research URL/title dedup, briefing content-hash, approval sweep set-restriction,
  per-hour metric dedup, read-only health). So an *accidental* double-fire is non-destructive — the
  lease model exists to prevent *waste and duplicate notifications*, not to prevent corruption.
- **Future (multi-node):** the lease becomes **explicit** — a job fires only if its runner holds a
  currently-valid lease for that `(job_id, fire_time)`. See §3–§4.

## 2. Single-Node Behavior (v1.0.1 — implemented design)

- One Nexus process runs `AsyncIOScheduler` inside the FastAPI lifespan.
- Jobs are re-registered declaratively at every startup (`MemoryJobStore`); losing the queue on
  restart is harmless because triggers are declarative and jobs idempotent.
- `coalesce=True` collapses missed fires during downtime into a single catch-up run.
- Failure isolation: per-job `max_instances=1`, per-run audit, engine error listener (see
  `scheduler-failure-model.md`).
- **Operational assumption:** exactly one Nexus instance writes to the single SQLite database
  (consistent with ADR-011 local-first). Running two instances against one SQLite file is
  **unsupported** in v1 — there is no cross-process lease, so both would fire every job (idempotency
  limits damage but duplicate notifications/work would occur).

## 3. Future Multi-Node Behavior

When Nexus scales beyond one process, the requirement is **fire-once-cluster-wide** per scheduled
instant. Design options (to be chosen in a future ADR — not now):

1. **Leader-elected scheduler:** one node is elected scheduler-leader and is the only node that
   fires jobs; workers execute. Election via a lease row / advisory lock / external coordinator.
2. **Per-job distributed lease:** every node runs a scheduler, but before firing, a node must
   atomically acquire a lease `(job_id, fire_time, owner, expires_at)`; only the winner runs. This
   reuses the **exact pattern already proven** in `system_outbox` lease-based delivery
   (`communication_outbox.lease_outbox_items`: atomic claim + `worker_id` + lease expiry +
   reclamation). The scheduler lease would be its sibling.
3. **External scheduler:** delegate firing to a distributed scheduler/queue (e.g. a clustered cron,
   Temporal) and keep Nexus jobs as plain workers. Heaviest; deferred per ADR-011.

The `SchedulerPort` abstraction means any of these is an adapter swap — **jobs and services do not
change**. Idempotency remains the backstop against lease races.

## 4. Future PostgreSQL Coordination

The migration to PostgreSQL (ADR-002 Phase 2) unlocks the cleanest multi-node coordination:

- **`SQLAlchemyJobStore` on PostgreSQL:** APScheduler can persist jobs/fire-times in PostgreSQL,
  giving durable, shared scheduling state across nodes.
- **Row-level locking / advisory locks:** PostgreSQL `SELECT … FOR UPDATE SKIP LOCKED` (a real,
  honored row lock — unlike SQLite's whole-DB lock, AP-101 §A-002/memory notes) makes the per-job
  lease (§3 option 2) trivial and contention-free, and would also let the existing outbox loops
  scale horizontally.
- **Coordination table:** a `scheduler_leases(job_id PK, fire_time, owner, acquired_at, expires_at)`
  table with an atomic upsert-if-expired claim — the natural Postgres expression of the lease model.
- **Concurrent writers:** PostgreSQL removes the single-writer SQLite constraint (audit RISK-002),
  so multiple Nexus nodes plus scheduler/outbox loops can write concurrently.

**None of this is built or required for v1.0.1.** It is recorded so the single-node implementation
deliberately avoids choices (e.g. hidden in-process-only state in jobs, non-idempotent side effects)
that would block the multi-node/PostgreSQL path later.

## 5. Design rules preserved for future scaling

To keep the door open, the v1.0.1 implementation MUST (and does, by design):
- keep jobs **idempotent** and **stateless** (no in-memory cross-run state);
- keep all firing decisions behind `SchedulerPort` (no direct APScheduler use in jobs/services);
- keep jobs invoking **services only** (so a future worker node can run the same job unchanged);
- audit every fire with a `correlation_id` (so cross-node tracing works later).
