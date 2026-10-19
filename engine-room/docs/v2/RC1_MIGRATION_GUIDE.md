# RC1 — Migration, Deployment, and Rollback Guide

Status: **Current as of RC1.** Complements `docs/v2/MIGRATION_FROM_V1.md` (the *conceptual*
v1→v2 mapping — no code, data, or deployment content) and `docs/v2/OPERATOR_GUIDE.md` (day-to-day
operation). This document is the practical companion: what to actually do to deploy v2, how to move
from v1, and how to roll back if something goes wrong. It documents what P17 found and what RC1 built
— it does **not** introduce a migration tool, a schema-versioning mechanism, or any other speculative
work neither program built.

---

## 1. The one fact that governs everything below

**v1 and v2 are two fully isolated strata.** Confirmed by direct AST-scanning in P17 (Phase 1): zero
cross-imports in either direction between `nexus/` (v1) and any `nexus_*` v2 package. They use different
persistence models entirely — v1 is async SQLAlchemy CRUD plus a separate append-only audit log; v2 is
synchronous, fully event-sourced (one SQLite file, append-only, ADR-007). **They do not share a database,
a schema, a process, or a config file.** Every recommendation in this guide follows from that fact:
running v2 never touches v1's data, and stopping v2 never affects v1.

---

## 2. v1 → v2 migration guide

### 2.1 What is supported today: a greenfield v2 deployment

The only migration path RC1 actually delivers is **running v2 standalone, starting from an empty durable
log.** Nothing in v1's existing pilot data (tasks, approvals, memory) moves into v2 automatically or
manually — there is no tool for it. If your goal is "start using the v2 constitutional spine," greenfield
is the supported path:

1. Choose a durable file path for v2, distinct from any v1 database.
2. Boot it with the new entrypoint (§4 has the full checklist): `nexus-v2 --db <path>`.
3. Register Goals/schedules against it via the composition-root API (`Scheduler.schedule_goal`, or a
   custom driver calling `build_constitutional_pipeline(...).coordinator.run(...)` directly).
4. v1 keeps running unchanged, serving whatever it already serves, for as long as you need it to.

### 2.2 What is *not* supported today: migrating v1's existing data into v2

P17 confirmed no tool, script, or documented procedure exists to migrate v1's pilot data into v2's event
log, and RC1 has not built one — doing so was explicitly out of scope (no new constitutional capability,
no speculative migration work). If your cutover *requires* v1's existing tasks/approvals/memory to appear
in v2, that is unaddressed work, not a gap you can work around with a script from this guide.

**The designed mechanism for this already exists on paper and is ratified, but is unimplemented:**
`adr/ADR-008-shadow-migration.md` — Recorded Shadow Adjudication. Each v1 decision, its v2 shadow, and
their classified diff would be recorded as events in the durable log; the v2 owner is proven equivalent
in shadow (side-effect-free) before becoming authoritative behind a per-owner feature flag, migrating one
constitutional owner at a time, Policy first. None of the five stages (Instrument → Shadow → Canary →
Default → Removal) are built. If a real v1-data cutover is ever required, ADR-008 is the design to build
against — not a new mechanism invented ad hoc.

### 2.3 Recommended sequencing if a real cutover is eventually planned

Not built in RC1; stated here only so a future program does not have to re-derive the ordering P17 and
this guide already establish:

1. Land ADR-008's Instrument/Shadow stages for the Policy Engine first (the universal governance leaf —
   see ADR-008 §3.4).
2. Prove shadow equivalence in production traffic before flipping any per-owner flag.
3. Only after Policy is stable, migrate the owners the Constitution's decision flow names next (Intent
   Resolution → Engineering Intelligence → Orchestration → Recovery → Human Interaction → Validation).
4. Data migration (moving v1's *existing* records, as opposed to migrating *decision authority* going
   forward) is a distinct, still-undesigned problem — ADR-008 migrates who decides, not historical rows.

---

## 3. Rollback procedure

Because the two strata are isolated, rollback is simple in both directions.

### 3.1 Rolling back a v2 deployment (v1 is never at risk)

v1 is never touched by running, upgrading, or removing v2 — there is no shared state to corrupt or undo.
To roll back v2 itself:

1. Stop the `nexus-v2` process (`Ctrl+C` / `SIGTERM` / `SIGINT` — `run_service` catches
   `KeyboardInterrupt` and exits cleanly; there is no in-flight write to lose, since every durable write
   is already committed by the time `tick()` returns — see P17's process-crash test for the underlying
   guarantee this rests on).
2. If the new version's behavior is the problem (not the data): redeploy the prior version of the code
   pointed at the **same** `--db` file. The durable schema is unversioned and has been stable across this
   program (§5 below) — every fix in RC1 (the scheduler linearization, the policy restart fix) is a
   behavioral/performance change over the *same* event shapes, not a schema change, so an older binary
   reads a newer file's events without incident, and vice versa.
3. If the *data* is the problem (a bad run polluted the log): there is no selective-delete or point-in-
   time restore built into the platform (event logs are append-only by design — ADR-001). Recovery means
   restoring the SQLite file from a filesystem-level backup taken before the bad run, or discarding it and
   starting over from an empty log if the affected history is not worth preserving. **Back up the durable
   file before any deployment you are not fully confident in** — a plain file copy is sufficient (SQLite
   WAL-safe copy: stop the process, or use `sqlite3 <path> ".backup <dest>"` for a safe live copy).

### 3.2 Rolling back a v1→v2 cutover (once one exists)

Not applicable today — no cutover mechanism is built (§2.2). Once ADR-008's flag-based migration lands,
rollback is a per-owner flag flip back to v1 authority (ADR-008 §3.2, the "Canary" stage's reverse-shadow
design) — documented here only so the eventual implementation has a stated rollback contract to satisfy,
not as something usable today.

---

## 4. Deployment checklist

What P17 found as real operational gaps, and which of them RC1 closed:

| Item | P17 finding | RC1 status |
|---|---|---|
| Entrypoint | None — an operator had to write a driver script | **Closed** — `nexus-v2` console script / `python -m nexus_scheduler` |
| Configuration | Zero environment-variable usage anywhere in v2; no "point this at a db path" story | **Partially closed** — the new entrypoint reads `NEXUS_V2_DB` (env var) and `--db`/`--tick-interval`/`--once`/`--log-level` (CLI flags); no other v2 subsystem takes config from the environment, and none needed to for this entrypoint to exist |
| Logging/Observability | No sink an operator could read after process exit | Closed in P17 (`LoggingObservability`); RC1's entrypoint wires it by default |
| Deployment artifact (Dockerfile stage, packaging) | None for v2 (v1's `docker/Dockerfile` launches v1 only) | **Not closed** — no Dockerfile stage exists for v2 yet; use the checklist below to run it directly or wrap it in your own container/service unit |
| Shutdown | No graceful `close()`/`shutdown()` anywhere in the durable infrastructure | **Not closed** — safe by construction (SQLite WAL atomicity, proven by P17's crash test) but still no explicit flush hook; `Ctrl+C`/`SIGTERM` is safe, not graceful |
| Schema migration | None — `CREATE TABLE IF NOT EXISTS` only, no version tracking | **Not closed, deliberately** — see §5 |

Steps to deploy `nexus-v2` today:

1. **Install.** `uv sync` (or `pip install .`) — the wheel's `packages` list already includes every v2
   package as of the P14–P16 commits on this branch.
2. **Choose a durable file path.** A fresh, empty path for a greenfield deployment. Put it somewhere with
   normal filesystem durability guarantees (SQLite WAL mode assumes a POSIX-ish filesystem; network
   filesystems are not validated).
3. **Choose a process supervisor.** `nexus-v2` is a foreground process with no daemonization built in —
   use systemd, a container orchestrator, `pm2`, or equivalent to keep it running and restart it on crash.
   A restart is always safe (§3.1, §5's replay/restart guarantees).
4. **Configure logging.** Wire a handler onto the `"nexus.infra"` and `"nexus.v2"` loggers (the entrypoint
   calls `logging.basicConfig` for you at the level you pass via `--log-level`; override in your own
   supervisor/config if you need structured output or log shipping).
5. **Start it.** `nexus-v2 --db /var/lib/nexus/v2.db --tick-interval 5 --log-level INFO` (defaults:
   `nexus_v2.db` in the working directory, 5-second tick interval, `INFO`).
6. **Register work.** The entrypoint authors no Goals itself — call `Scheduler.schedule_goal(...)` (or
   `.schedule_operation(...)`) against the same durable file from a separate short-lived script/process,
   or extend `bootstrap()`'s returned `PlatformContext` in your own driver if you need programmatic
   control in the same process.
7. **Verify it's alive.** Query `nexus_operations` (via `PlatformContext.operations`) for a health
   summary, or tail the configured log — every tick that dispatches something logs
   `"tick dispatched N occurrence(s)"`.
8. **One-shot / cron mode.** `nexus-v2 --once` runs exactly one tick and exits — use this instead of the
   long-running loop if you'd rather drive timing from an external scheduler (cron, a Kubernetes
   CronJob) than keep a process alive between ticks.

---

## 5. Compatibility notes

- **No schema versioning exists.** The durable schema uses `CREATE TABLE IF NOT EXISTS` only
  (`nexus_infra/durable.py`) — idempotent bootstrap, no migration mechanism, confirmed unchanged by RC1.
  **Treat the durable schema as frozen** until a real migration mechanism is built (P17's own
  recommendation, restated here as the operative policy): do not hand-edit the SQLite file's schema, and
  do not assume a future version can silently reshape it out from under an existing durable file.
- **RC1 introduced zero schema changes.** Every fix in this program (scheduler linearization, policy
  restart-safety) changes internal control flow, not the shape of any event payload or table — a durable
  file created before RC1 and one created after are schema-identical.
- **Version signals still disagree** (a pre-existing P17 finding, not fixed by RC1 — fixing it is
  release-hygiene, not a blocker): `pyproject.toml` says `0.1.0`; every `nexus_*` v2 package's
  `__version__` says `2.0.0a1`; `CHANGELOG.md`'s latest entry is v1-scoped. Do not infer v2's release
  maturity from any of these numbers today.
- **Dependency footprint is unchanged by RC1.** The v2 spine's only third-party dependency remains
  `pydantic` (P17 Phase 7.5, AST-verified across all packages); RC1 added no new dependency (the
  entrypoint uses only `argparse`, `logging`, `os`, `sys`, `time` — all stdlib).
- **Python 3.12+ required** (`pyproject.toml`'s `requires-python`), same as before RC1.

---

## 6. Upgrade validation

How to confirm a new build of v2 (this branch, or a future one) is safe to deploy over an existing durable
file, before you actually cut over:

1. **Run the full v2-scoped test suite** (the exact set CI runs — see `.github/workflows/core-ci.yml`'s
   pytest job for the current package list): `pytest tests/unit/nexus_* tests/integration --noconftest`.
   Expect the same shape RC1 verified: all tests passing, mypy-strict clean, ruff clean.
2. **Re-run the benchmark and scale scripts** (`scripts/p17_benchmark.py`, `scripts/p17_scale.py`) and
   compare against the numbers in `docs/v2/RC1_PRODUCTIZATION_REPORT.md` — a material regression (order-
   of-magnitude slower, or a return of quadratic scheduler scaling) is a signal to hold the upgrade.
3. **Copy the production durable file to a scratch location and boot the new version against the copy**
   (`nexus-v2 --db /tmp/scratch-copy.db --once`) before pointing it at the real file. Confirm it starts
   without error and `platform.scheduler.schedules()` / `platform.operations` report the state you expect
   — this exercises the exact "restart over a reopened file" path `tests/integration/test_v2_entrypoint.py`
   covers, against your real data instead of a synthetic fixture.
4. **Only then repoint `--db` at the production file** and restart under supervision. Because the schema
   is frozen (§5) and every RC1 fix is behavior/performance-only, this is expected to be a safe, ordinary
   restart — not a migration.
