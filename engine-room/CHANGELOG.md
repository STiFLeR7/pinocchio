# Changelog

All notable changes to Nexus will be documented in this file.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)

> Reconstructed in AP-104 (v1.0.1) from the git history and blueprint implementation reports, after the
> onboarding audit found the changelog had omitted the actual v1.0.0 release. See
> [release-history-reconstruction.md](blueprint/implementations/v1.0.1/release-history-reconstruction.md).

---

## [2.5.0] — 2026-09-30 — "Accountable Goal Execution"

### Added — Phases 1–6

- **Operator-facing end-to-end path (Phase 1).** A technical operator can submit a goal through the
  existing constitutional spine and inspect/request continuation at explicit boundaries.
- **Grounded understanding and plans (Phase 2).** Plans retain repository source references, work-item
  objectives, dependencies, assumptions, and unresolved clarification needs before actuation.
- **Constrained first-party actions (Phase 3).** Repository writes and named allow-listed test commands
  are bound to a frozen action request, workspace, Policy decision, and explicit Approval Exchange event.
  The CLI does not accept arbitrary executable argv as a governed test command.
- **Independent outcome validation (Phase 4).** Declared file-hash and JUnit conditions determine the
  outcome verdict; runtime completion is reported separately and cannot establish acceptance.
- **Evidence-bound Knowledge (Phase 5).** Only independently accepted results can be promoted as proven
  guidance; failed, partial, unknown, and out-of-scope evidence is excluded or kept reviewable.
- **Technical operator pilot (Phase 6).** Five disposable repair fixtures exercise approval, evidence
  validation, Knowledge disposition, replay, and SQLite plus artifact-sidecar backup/restore.

### Validated pilot outcomes

- P1 addition, P2 normalization, and P3 clamp passed independent edit and test validation; the one
  operator rated all three useful, and Knowledge accepted their evidence.
- P4's intentionally incorrect title-case repair failed both declared conditions and was rejected by
  Knowledge.
- P5's source repair passed its file-hash condition but its deliberately missing JUnit report produced
  `requires_review`; it was not promoted as proven Knowledge.
- The operator reported zero false denials. All five runs retained complete event lineage; no unauthorized
  action, false `PASSED` verdict, or completed-run replay duplication was observed.
- The live-Claude strict suite passed 3,261 tests with `-W error`, zero skips, and zero warnings. Ruff
  check, Phase 6 Ruff format/type checks, and `uv build` passed. Whole-repository Ruff format check still
  reports 55 pre-existing findings outside Phase 6; they are disclosed in
  [`docs/phase6/RELEASE_REVIEW.md`](docs/phase6/RELEASE_REVIEW.md).

### Scope and migration notes

- Pilot evidence comes from synthetic, disposable fixture repositories. It does not establish reliability
  for arbitrary real repositories, sustained operation, or autonomous repair. The deterministic Intent
  route required a recorded software-domain prefix for all five pilot requests; this is an input
  intervention, not proof that unmodified request text resolved.
- v1 (`nexus/`) and v2 (`nexus_*`) remain independent codebases with no shared schema, process, or
  execution path. This v2 release version does not change v1 behavior or migrate v1 data.
- Phases 1–6 introduced no durable schema migration. This statement does not add schema versioning or an
  upgrade mechanism to the existing v2 store.
- The controlled pilot is limited evidence and does not authorize broader reliability claims. See
  [`docs/releases/V2_5_RELEASE_REPORT.md`](docs/releases/V2_5_RELEASE_REPORT.md) for release evidence and CI record.

## [2.0.0] — 2026-07-23 — "Constitutional Spine"

> First stable release of the **v2 constitutional platform** — a from-scratch, event-sourced
> reasoning/execution spine (~30 `nexus_*` packages), architecturally and operationally independent of
> the v1 lineage below (zero cross-imports, confirmed both directions). Every `nexus_*` package already
> self-versioned as `2.0.0a1` throughout its P0–P17 build-out; this release graduates that alpha to
> stable. It does **not** supersede or replace v1 — the two run as separate processes
> (`python -m nexus` / `python -m nexus_scheduler`) sharing one repository. See
> `docs/v2/V1_RELEASE_READINESS_REPORT.md` for the full audit, validation, and GA evidence behind this
> entry.

### Added

- **The constitutional reasoning spine** — thirteen single-owner capabilities (Understand → Reason →
  Ground → Contextualize → Plan → Coordinate → Execute → Act → Observe → Validate → Recover → Reflect →
  Learn), fused into one deterministic Goal→Knowledge driver (`nexus_workflows.spine`), governed
  throughout by the Policy Engine and Human Interaction, measured throughout by Observability and
  Operations — built across the P0–P17 program and ratified in `docs/v2/ARCHITECTURE_CONSTITUTION.md`
  against 39 architectural invariants and ADR-001 through ADR-004/007/008.
- **Durable, event-sourced persistence** — an append-only SQLite/WAL event log is the single source of
  truth for every subsystem; all state and checkpoints are deterministic projections of that log
  (INV-13/14), enabling exact replay and restart from any interruption point.
- **Governed autonomy** — the Constitutional Scheduler (`nexus_scheduler`) drives one-time, recurring,
  and delayed goal dispatch under `AutonomyMode` (fully-automatic or human-governed), fronted by the
  Approval Exchange (`nexus_approval`) and a read-only Operations plane (`nexus_operations`).
- **The v2 production entrypoint** — `python -m nexus_scheduler` (`nexus-v2` console script) boots the
  full durable spine and drives it against the real wall clock; introduced additively in RC1, alongside
  v1's untouched `python -m nexus` entrypoint.

### Fixed (RC1 — Release Engineering & Production Hardening)

- Scheduler tick dispatch rewritten from O(n²) to linear in the number of tracked schedules, with no
  behavioral change (`nexus_scheduler/scheduler.py`).
- Policy registration and Runtime registration both made restart/re-actuation-safe under a real,
  advancing wall clock — a class of bug invisible under every pre-RC1 test's fixed-clock convention,
  where the same deterministic identifier re-emitted at a genuinely different timestamp previously
  raised `DuplicateEventError` on the second process start.
- `adr/ADR-009-runtime-selection-ownership.md` proposed to resolve an INV-37 ownership contradiction
  (currently **Proposed**, not yet ratified — see Known Limitations).

### Fixed (RC2 — Execution Identity & Session Isolation)

- **Cross-goal Runtime Session collision.** Runtime Session identity was derived from a work-item key
  alone (unique only within one plan), so two goals whose plans produced a same-keyed work item minted
  the identical Runtime Session id and collided on every downstream `runtime.*`/`validation.*` event
  scope. Fixed by including the already-goal-scoped Execution Session id (`nexus_execution/actuation/dispatch.py`).
- **Cross-goal scope-lookup collision.** The Execution→Validation seam resolved a node's runtime scope
  by scanning the *entire* durable log (every goal ever run in the process) keyed by bare node id, so
  two goals sharing a node key could resolve to the wrong (or an overwritten) scope. Fixed by filtering
  to the current execution session (`nexus_workflows/spine/bridge.py`).
- **Silent cross-goal state adoption (the deepest defect found).** Restart-seeding scanned the entire
  durable log for the *first* Goal/Plan/ExecutionState of each type, with no check that it belonged to
  the request being resumed. A second goal sharing a durable log with an already-completed first goal
  would silently adopt that goal's state, skip its own Intent→Actuation entirely, and report success
  having never actually run. Fixed by matching reconstructed artifacts against the goal identity the
  current request actually resolves to (`nexus_workflows/spine/coordinator.py`).
- All three fixes are additive propagation of identity that already existed in the codebase — no new
  identity concept, no ownership change, no ADR required. Full evidence, reproduction, and regression
  tests in `docs/v2/RC2_EXECUTION_IDENTITY_REPORT.md`.

### Changed

- Version identifier reconciled platform-wide: every `nexus_*` package's `__version__` graduated from
  `2.0.0a1` to `2.0.0`; `pyproject.toml`'s `[project] version` (previously a stale, unrelated `0.1.0`)
  now reads `2.0.0`. Resolves the four-way version disagreement `docs/v2/P17_PRODUCTION_READINESS_REPORT.md`
  §7.2 flagged as a pre-GA blocker.
- `pydantic` dependency constraint tightened to `>=2.0,<3` (was unbounded) so a future breaking major
  version cannot silently break the build.
- Added the repository's `LICENSE` file (MIT) — previously declared in `pyproject.toml` and referenced
  by a `README.md` badge, but the file itself did not exist.

### Known Limitations

- **No v1→v2 data migration tool.** The two strata use entirely different persistence models (v1:
  async SQLAlchemy CRUD + a separate audit log; v2: synchronous, fully event-sourced) and remain fully
  isolated. `ADR-008-shadow-migration.md` documents a designed-but-unbuilt migration path. v2 today only
  supports a greenfield (empty durable log) start.
- **Durable schema is unversioned.** `nexus_infra/durable.py` uses `CREATE TABLE IF NOT EXISTS` only —
  idempotent bootstrap, no migration mechanism. A future schema change has no upgrade path for an
  existing durable file.
- **ADR-009 (INV-37 runtime-selection ownership) remains unratified** — Proposed status, carried forward
  from RC1.
- **Two frozen-contract candidates remain un-frozen** despite meeting the freeze trigger: `engineering_strategy`
  and `repository_understanding`. Their shape can still change without the formal process the other 18
  frozen contracts get.
- **`nexus_briefings` and `nexus_operator` remain unwired** into the running product (real, tested code;
  zero live callers) — flagged since P17, unchanged.
- A latent, not-currently-triggered identity-collision shape remains in `GraphNode.identifier` and its
  checkpoint reference (both pure functions of a work-item key alone) — safe today only because every
  consumer looks them up inside an already goal-scoped container; documented in
  `docs/v2/RC2_EXECUTION_IDENTITY_REPORT.md` §9 as a fast-follow, not a defect in the current code path.
- `ConstitutionalPipeline.execution_graph()`/`execution_state()` (read-only inspection methods) share the
  same un-scoped-reconstruction shape RC2 fixed on the restart path — dormant (cannot corrupt the log,
  only a read-path ambiguity), not fixed, documented as a fast-follow.
- Recovery is invoked with `checkpoint_ref=None` unconditionally — an independent INV-18 gap noted during
  RC2's audit, unrelated to identity, not in RC2's scope.

### Migration Notes

- No database migration required for a fresh v2 deployment — the durable schema is created from the
  current models on first run.
- v1 and v2 are independent processes; running v2 alongside an existing v1 deployment requires no changes
  to v1 and shares no runtime state.
- See `docs/v2/RC1_MIGRATION_GUIDE.md` for the full v1→v2 migration guide, rollback procedure, and
  deployment checklist.

---

## [1.1.0] — 2026-06-25 — "Containment"

Pilot operational release. Validated through a **real operational bring-up** (no mocks) — boot,
onboarding, scheduler, email, research, briefing, runtime, recovery, and Discord all exercised on
real infrastructure (**9/9 stages live-validated**). Classified **Pilot Ready** (not Production
Ready). Full evidence in `blueprint/implementations/v1.1.0/`.

### Branding

- **Hermes → Nexus Agent.** The autonomous planning/research runtime is renamed throughout code,
  tests, ADRs, and documentation. Registry id is now `nexus`; runtime records persist `runtime="nexus"`.
  `nexus/execution/runners/hermes.py` → `nexus_agent.py` and `hermes_tools.py` → `nexus_agent_tools.py`
  (git history preserved). Third-party Nous Research / `hermes-agent` references and historical tags
  (`hermes-experimental`, `hermes-pilot`) were intentionally **not** renamed.

### Architecture

- No architectural changes. Runtime registry, governance gates, sandbox boundary, scheduler ports,
  and memory/event-sourcing boundaries preserved. ADR history intact.

### Runtime

- **Nexus Agent: Experimental → Pilot.** Fail-fast initialization (refuse to start without an LLM
  capability), operator-tunable `execution.agent_max_steps`, honest terminal lifecycle
  (`completed`/`failed`/`timed_out`/`cancelled`), cancellation wiring, and `resume_goal`
  checkpoint recovery (H-2/H-4).
- **Multi-provider LLM gateway** — Groq → Zenmux → OpenRouter (free models) fallback chain;
  resilient to single-provider 402/429 (`nexus/intelligence/openrouter.py`).
- Orchestrator exit-status finalization honors the agent's truthful terminal status
  (`resolve_exit_status`, H-4).

### Governance

- A-001 fail-closed owner authorization verified live at boot; `RepositoryValidated` /
  `RuntimeAuthorized` audited per execution. Config now also reads `DISCORD_OWNER_ID` (operator-
  friendly alias) for owner-id resolution.

### Sandbox

- **Pilot Safe** (Track S): default-secure (`enabled=False`, `provider=local`, `network=none`,
  `fs=restricted`), execution fails closed, S-3 startup gate enforced.

### Research

- Live-validated: 20 findings parsed from a live RSS feed, LLM-scored, and persisted
  (`research.completed`).

### Scheduler

- Live-validated: audited jobs executing (`scheduler.job.started:4` / `completed:4`) with metrics
  and failure isolation.

### Operational Validation

- New `python -m nexus onboard` — safe, read-only staged operator onboarding (`nexus/onboarding.py`).
- Email (SMTP) real delivery after a one-line double-STARTTLS fix
  (`nexus/communication/email/service.py`).
- Discord real gateway delivery (bot → guild → `#general`, message id confirmed).
- Recovery: interrupt → fresh-adapter resume → completion, no corruption, audit continuity.
- Config alignment: `NOTIFY_SMTP_*` / `NOTIFY_EMAIL_FROM` mapped into the email config so the
  existing SMTP service delivers without a parallel credential store. `.env` remained the single
  source of truth (never rewritten).

### Breaking Changes

- **None for persisted data or external APIs.** The runtime id `hermes` and runner type
  `hermes_agent` still resolve (registry alias + retained enum member). Source imports of
  `HermesRuntimeAdapter` still work via a module-level alias.
- Internal module paths changed: import the agent runtime from
  `nexus.execution.runners.nexus_agent` (the old `hermes` module path no longer exists).

### Migration Notes

- No database migration required. On a fresh deployment the schema is created from the current
  models (`create_all`); existing databases with the v1.1.0 task columns need no change.
- Operators using the singular `DISCORD_OWNER_ID` env key are now supported directly.
- LLM defaults changed to free OpenRouter models; set `GROQ_API_KEY` / `ZENMUX_API` to enable the
  full fallback chain, or supply a paid/BYOK OpenRouter key for sustained load.

### Known Issues

- Free-tier LLM rate-limits under sustained load (mitigated, not eliminated, by the fallback chain).
- `create_all`-only schema management; Alembic migrations incomplete (manual recreate handled drift).
- `.env` `DISCORD_*_CHANNEL` ids not yet read into `settings.discord.channels` (delivery works).
- Gemini / Claude runtimes remain generic shell runners (Experimental).
- No production web `SearchProvider` for agent tools.
- In-code version string (`nexus/__init__.py`, `pyproject.toml`) still reads `0.1.0` — pre-existing
  documented debt; source bump deferred to v1.2 (out of release-workstream scope).

---

## [1.0.1] — 2026-06-24 — "Alignment"

A correctness, safety, and operational-completeness release. **No new features.** Every change traces
to an accepted onboarding-audit finding (A-001…A-006).

### Fixed

- **A-001 — Fail-open owner authentication.** Approval authorization now **fails closed**: the
  application refuses to start when no `discord.owner_ids` are configured, and the approval engine
  rejects authorization when owners are unset. (AP-102: `nexus/api.py`, `nexus/approvals/service.py`.)
- **A-002 — Execution timeout mismatch.** Runtimes previously read a non-existent config field and
  silently fell back to 300s. Added `resolve_execution_timeout(...)` honoring the ADR-010 per-runtime
  tiers and clamping to `execution.hard_limit`. (AP-102: `nexus/execution/runners/`.)

### Added

- **A-003 — Scheduler foundation.** APScheduler-backed, single-node scheduler behind a replaceable
  `SchedulerPort`, with six audited jobs — `research_collection`, `daily_briefing`,
  `approval_expiration_sweep`, `metrics_aggregation`, `outbox_health` (read-only),
  `checkpoint_health` (read-only). New `SCHEDULER_JOB_STARTED/COMPLETED/FAILED/SKIPPED` events,
  additive `SchedulingConfig`, and read-only `OutboxHealthService` / `CheckpointHealthService`.
  (AP-103B: `nexus/scheduling/`, `nexus/gateway/outbox_health.py`, `nexus/memory/checkpoint_health.py`.)
- **A-004 — Documentation alignment.** Realigned `README.md`, `blueprint/STATUS.md`,
  `blueprint/ROADMAP.md`, this changelog, and the blueprint landing page to reality; added
  `repository-state-map.md`, `documentation-drift-analysis.md`, `architecture-status-summary.md`,
  `release-history-reconstruction.md`, and the alignment reports. (AP-104.)

### Pending

- **A-005** — Nexus runtime reality audit (AP-105).
- **A-006** — Sandbox safety review.

### Known issues / residual debt

- In-code version string (`nexus/__init__.py`, `pyproject.toml`) still reads `0.1.0` while the release
  tag is `v1.0.0` (source/config change, out of the documentation-only AP-104 scope).
- `/api/v1/status` reports subsystems as literal `"stub"`; health is a boot-time boolean, not live.
- Concrete Gemini/Claude runtimes are generic shell runners; Nexus contains simulated branches.
- Default sandbox `provider="local"` provides no isolation.
- Alembic migrations incomplete; `create_all` is the current schema source.

---

## [1.0.0] — 2026-06 — "Operational Intelligence"

> Git tag `v1.0.0` (`4566020`, `aa3e527`). The first released governed-execution control plane.

### Added

- **Approval system** — un-bypassable, database-backed approval gate fronting all execution, fully
  audited (`nexus/execution/service.py`, `nexus/approvals/service.py`).
- **Runtime governance** — 11-gate governance authorizing every execution decision
  (`nexus/execution/governance.py`).
- **Runtime registry + adapter split** — CLI/Agent adapters for Gemini, Claude, and Nexus runtimes
  (AP-301…AP-304; `nexus/execution/runners/`).
- **Event-sourced memory** — immutable `audit_log`, checkpoint replay, resumable context
  (`nexus/memory/`).
- **Transactional + communication outbox** — lease-based delivery with backoff, dead-lettering, and
  audit on success/failure (`nexus/gateway/`).
- **Research engine** — crawl→dedup→summarize→persist with resumable runs (RSS/Atom).
- **Daily briefing engine** — operational briefing generation and dispatch.
- **Metrics persistence** — metric collection and flush.
- **Task management** — full guarded lifecycle with Discord CRUD.
- **Discord + Email communication** adapters; OpenRouter intelligence gateway.
- Accepted onboarding audit (`blueprint/onboarding/`, `NEXUS_FIRST_IMPRESSION.md`), maturity 6.0/10.

### Known issues at release (addressed in v1.0.1)

- Fail-open owner authentication (A-001); execution-timeout field bug (A-002); **no scheduler** so
  research/briefing/metrics/expiry never fired autonomously (A-003); documentation drift (A-004);
  Nexus simulated behaviors (A-005); default-off sandbox isolation (A-006).

---

## [0.0.1] — 2026-06-19

### Added

- Repository initialized; `docs/` directory with foundational documents; initial `.git` repository.
