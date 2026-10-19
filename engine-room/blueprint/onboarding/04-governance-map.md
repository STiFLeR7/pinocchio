# 04 — Governance Map (Architecture Review: Governance Layer, Approval Gate, Policy Service, ADR model)

> Read-only audit. Governance in Nexus operates at two levels: **runtime governance** (the
> pre-execution gate in `nexus/execution/governance.py`) and **project governance** (ADRs +
> blueprint discipline). Both are covered here. Evidence cited as `file:line`.

---

## A. The Approval Gate — the load-bearing safety invariant

**Execution cannot bypass approval. This is the single most important guarantee in Nexus and it is
genuinely enforced** (verified by reading every subprocess-spawn path):

- `ExecutionService.start_execution` calls `check_approval_gate(task_id)` first and raises
  `ExecutionEngineError("Task does not have an active approved status.")` if it returns False
  (`execution/service.py:43-45`).
- `check_approval_gate` returns True only if an `APPROVED` `ApprovalRecord` exists for the task
  (`approvals/service.py:236-248`) — it reads the **database**, not Discord, so an offline bot
  cannot cause a bypass.
- The orchestrator reaches execution only via the `APPROVAL_GRANTED` event handler
  (`orchestrator.py:79-101`).
- Subprocess spawning is architecturally confined to `nexus/execution/`
  (`service-boundaries.md:103`).

**Owner authorization** — Only configured owners can decide an approval. Enforced in two places:
the Discord button handler (`bot.py:52-58`) and the service (`approvals/service.py:94-95`).
⚠ **Caveat:** if `owner_ids` is empty, the check is skipped (`approvals/service.py:94`,
`bot.py:53`) and the config default is `owner_ids=[]` (`config.py:42`) — a misconfigured deployment
grants approval to anyone. Treat configuring owner IDs as a security-critical setup step.

**Concurrency safety** — `evaluate_approval` locks the row with `with_for_update` and rejects
already-decided gates (`approvals/service.py:97,104-105`), preventing double-decision races.

**⚠ Expiration is not enforced in production** — `sweep_expired_approvals` (`service.py:184`) is
**never scheduled** (verified: callers only in `scripts/verify_phase2_mvp.py:317` and tests).
Expiry is only caught opportunistically if an owner clicks after expiry (`service.py:108-118`).
Consequence: expired approvals can sit `PENDING` forever and their parent tasks stay `BLOCKED`
indefinitely, emitting no `APPROVAL_EXPIRED` event. This contradicts ADR-009 ("runs every hour",
`ADR-009:72-79`). It is also a *semantic* divergence: ADR-009 says expiry must **not** auto-reject
and should route to a review queue with notification (`ADR-009:11-15,30-33`), but the code instead
**cancels the parent task** with no notification (`service.py:209-210`).

---

## B. Runtime Governance Gate  (`execution/governance.py`)

**Purpose** — Enforce all safety/allowlist constraints before any process is spawned; audit every
decision (`governance.py:32-33,39-58`).

**Dependencies** — `PolicyService` (policy reads), `health` (control-plane liveness), the `git` CLI
(branch checks), and the `RepositoryRegistryRecord`/`ApprovalRecord`/`ExecutionRecord`/
`GovernanceSemaphoreRecord`/`AuditLogRecord` models.

**Inputs** — `(task_id, working_dir, command, runtime)` via `validate_execution`
(`governance.py:60-66`), invoked by every adapter's `validate()`/`validate_goal()`.
**Outputs** — the matching repo record on success (`governance.py:653`); otherwise raises
`RepositoryGovernanceError` + writes an audit row.

**The 11 ordered gates** (`governance.py:60-653`):

| # | Gate | Evidence |
|---|---|---|
| 0 | Control-plane health (`health.is_healthy()`) | `governance.py:71-84` |
| 1 | Runtime in system `allowed_runtimes` policy | `governance.py:86-102` |
| 2 | `task.runtime_policy` == `required_runtime_policy` (default `approved`) | `governance.py:113-127` |
| 3 | An `APPROVED` approval record exists | `governance.py:129-147` |
| 4 | `working_dir` is inside a registered repo (realpath containment) | `governance.py:149-175` |
| 5 | Repo is active (`status=="active"` and `is_active`) | `governance.py:177-188` |
| 6 | Runtime allowed on that repo (`allowed_runtimes`) | `governance.py:197-219` |
| 7 | `task.execution_profile` allowed on repo (`allowed_profiles`) | `governance.py:221-238` |
| 8 | Approval decider is in repo `owner` list | `governance.py:240-257` |
| 9 | Per-repo concurrency semaphore + capacity (min of global/override) | `governance.py:260-388` |
| 10 | Branch constraints (blocked → protected → allowed, `fnmatch` globs) | `governance.py:396-613` |
| 11 | Command blacklist (substring match) | `governance.py:615-642` |

The semaphore is released on **every** exit path, success or failure
(`governance.py:366-651`); acquisition uses exponential backoff + jitter on SQLite
`database is locked` (`governance.py:299-326`).

**Critical invariants** — working dir must be inside a registered active repo; the semaphore must
always be released; every rejection is audited.

**Failure modes** — git missing/timeout → reject (`governance.py:429-470`); lock exhaustion →
reject; **substring blacklist is both bypassable** (e.g. `rm  -rf /` double space, quoting,
env-var indirection) **and over-broad** (false positives) — `if pattern in command`
(`governance.py:621`), defaults `["rm -rf /", "sudo ", "mv /etc", ":(){ :|:& };:"]`
(`policy_defaults.py:9`).

**Recovery** — backoff retry on locked semaphore; guaranteed lock release.

**Extension points** — All lists are policy-driven via `PolicyService`; per-repo override columns
exist (`models.py:506-513`).

---

## C. Policy Service  (`memory/policy_service.py`)

**Purpose** — Externalize governance policies into the `system_policies` table with versioning and
history, replacing the hardcoded `policy_defaults.py` ("legacy fallbacks", `policy_defaults.py:1`).

**Key behaviors**:
- **Fail-closed reads** — a DB error during `get_policy` audits `PolicyRegistryUnavailable` and
  **raises** `RepositoryGovernanceError` (`policy_service.py:59-69`); a missing key falls back to a
  code default with a `PolicyFallbackUsed` audit (`:77-88`); no default → `PolicyMissingError`
  (`:90-95`). This is the correct posture for a security gate and must never become fail-open.
- **Optimistic locking** — `update_policy` matches `WHERE version == current_version`; on
  `rowcount==0` it audits `PolicyVersionConflict` and raises (`:97-149`), then writes a history row
  (`:151-172`).
- **Idempotent seeding** at startup (`api.py:92-94` → `seed_default_policies`, `:174-285`).

**Gap** — Seeding writes `concurrency_retry_count`/`concurrency_retry_timeout` (`:244-245`) which
have **no schema-validation branch** in `_validate_policy_schema` (`:209-224`) — silently
unvalidated.

**Seeded policy keys** (defaults, `policy_defaults.py`): `allowed_runtimes`
(`["gemini","claude","nexus"]`), `global_command_blacklist`, `default_concurrency_limit` (3),
`concurrency_retry_count` (5), `concurrency_retry_timeout` (5.0), `required_runtime_policy`
(`"approved"`).

---

## D. Project Governance — the ADR + blueprint model

**How decisions are recorded.** Architecture decisions live as ADRs in `blueprint/DECISIONS/`
(21 files). Each carries Date, Status, "Decided By" (owner for binding ones), Context, Decision,
Consequences. Owner-level Open Questions are tracked in `blueprint/GAPS_AND_RISKS.md` and closed by
minting an ADR (the OQ→ADR map is `GAPS_AND_RISKS.md:328-350`). Decisions are **superseded, not
overwritten** (e.g. ADR-006 "Supersedes: ADR-001", `ADR-006-approved-tech-stack.md:7`) — the same
append-only immutability the runtime applies to its audit log.

**How phases are gated.** Phase transitions require Go/No-Go ADRs with numeric readiness scores:
Phase 1 authorized at 95/100 (`ADR-final-preimplementation-review.md:36-39`); Phase 2 at
96/100 compliance + 98/100 readiness (`ADR-phase1-retrospective.md:46-58`).

**"Blueprint is project memory" in practice** — `blueprint/` is the durable human-readable
counterpart to the event-sourced runtime memory (`README.md:213`): `DECISIONS/` (ADRs), `phases/`
(plans/AP breakdowns), `reports/` (gap analyses, readiness, retrospectives), `architecture/`
(designs), plus `ROADMAP.md`/`STATUS.md`. Discipline: "New items are appended. Resolved items are
marked but never deleted." (`GAPS_AND_RISKS.md:15`).

**⚠ Governance integrity issue: blueprint is out of sync with code.** Operating Rule 9 requires the
blueprint to remain synchronized, but `STATUS.md` (Phase 1 only), `ROADMAP.md` (Phases 2-7 "Not
Started"), `README.md` (all phases "Pending", v0.1.0/pre-alpha), and `CHANGELOG.md` (up to 0.0.1)
all predate the shipped Phase 2/3 work and the v1.0.0 tag. ADR numbering also collides (ADR-015
appears on two files; several runtime ADRs are unnumbered). See `10`/`11`.

---

## Governance gap analysis

**Excellent** — The approval gate is genuinely un-bypassable and DB-backed; the 11-gate runtime
governance is thorough and audits every decision; policy reads are fail-closed with optimistic
locking and history; ADR governance mirrors the product's own immutability philosophy. Governance
is the strongest pillar of Nexus (12 dedicated tests, `tests/unit/execution/test_governance.py`).

**Missing** — Scheduled approval expiration; expiration notifications + review queue (ADR-009);
audit logging of *unauthorized* Discord attempts (ADR-008 requires it, `bot.py:52-58` does not);
the `DiscordAuthGuard` class and `EmailProvider` protocol mandated by ADR-008/ADR-007.

**Risky** — Empty `owner_ids` disables auth (`config.py:42`); substring command blacklist is
bypassable/over-broad; expired approvals strand tasks in `BLOCKED`; blueprint/code desync undermines
the "blueprint is authoritative" rule.

**Never change** — `check_approval_gate`→raise in `start_execution` (`execution/service.py:43-45`);
fail-closed policy reads (`policy_service.py:59-95`); semaphore release symmetry
(`governance.py:644-651`); `with_for_update` on approval transitions; the ADR supersession
(append-only) discipline.

**Monitor** — Count of `PENDING` approvals past `expires_at`; tasks stuck in `BLOCKED`;
`control_plane_marked_unhealthy` events (`health.py:38`); governance rejection audit rates.

**Improve** — see `12-improvement-opportunities.md`.
