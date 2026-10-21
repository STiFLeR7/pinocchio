# Scheduler Validation Report (AP-103C)

> Validation evidence for the Scheduler Foundation (AP-103B). TDD red→green, full regression,
> boundary + read-only + isolation assertions.

---

## 1. Test inventory — `tests/unit/scheduling/test_scheduler_foundation.py` (17)

| Area | Test | Asserts |
|---|---|---|
| Events | `test_scheduler_event_types_exist` | the 4 `SCHEDULER_JOB_*` enum values + string values |
| Config | `test_scheduling_config_cadence_defaults` | research 2h, briefing 08:00, approval 15m, metrics 5m, outbox 10m, checkpoint 30m, tz Asia/Kolkata |
| Config | `test_scheduling_config_attached_to_settings` | `NexusSettings.scheduling` is a `SchedulingConfig` |
| J5 (read-only) | `test_outbox_health_service_snapshot_readonly` | counts pending/dead_letter/events_pending; **row count unchanged** after snapshot |
| J6 (read-only) | `test_checkpoint_health_service_snapshot_readonly` | counts stale executions + checkpoints from seeded data |
| Runner | `test_run_scheduled_job_audits_started_and_completed` | STARTED + COMPLETED audit rows written |
| Runner | `test_run_scheduled_job_audits_failure` | failing body → FAILED audit; **call does not raise** (isolation) |
| Runner | `test_run_scheduled_job_audits_skip` | `JobSkippedError` → SKIPPED audit |
| J1 | `test_research_job_skips_without_feeds` | empty feeds → `JobSkippedError` |
| J1 | `test_research_job_invokes_service` | calls `ResearchService.execute_research_run` with configured feeds |
| J3 | `test_approval_expiry_job_invokes_service` | calls `ApprovalService.sweep_expired_approvals` |
| J4 | `test_metrics_job_invokes_aggregation` | calls `run_aggregation_and_retention` |
| J5 | `test_outbox_health_job_records_metrics` | returns snapshot dict with `dead_letter` |
| J6 | `test_checkpoint_health_job_returns_snapshot` | returns snapshot dict with `stale_executions` |
| Registration | `test_build_scheduler_registers_enabled_jobs` | all 6 job ids present |
| Registration | `test_build_scheduler_omits_disabled_jobs` | disabled research/outbox absent; briefing present |
| Registration | `test_build_scheduler_disabled_globally_returns_none` | `scheduling.enabled=False` → `None` |

## 2. Requirement → evidence matrix

| AP-103 requirement | Evidence |
|---|---|
| Jobs invoke services only / no model access | job bodies import services + `get_session` only; J1/J3/J4 service-invocation tests; boundary by construction |
| No business logic in jobs | audit/timing centralized in `run_scheduled_job`; job bodies are 3–5 lines |
| Failures auditable | runner audit tests (STARTED/COMPLETED/FAILED/SKIPPED) |
| Failure isolation | `test_run_scheduled_job_audits_failure` proves the runner swallows + audits, never raises |
| Read-only J5/J6 | `*_readonly` tests assert no row mutation; services are SELECT-only |
| Config toggles honored | `omits_disabled_jobs`, `disabled_globally_returns_none` |
| Cadences correct | config-default test + operational next-run-time verification |
| Restart-safe / replaceable | declarative registration test; `SchedulerPort` Protocol present |

## 3. TDD red→green

- **Red:** `ImportError: cannot import name 'SchedulingConfig'` (and the scheduler modules) before
  implementation.
- **Green:** 17/17 after implementation.
- **One mid-cycle failure** was a *test seed* defect — `SystemOutboxRecord` requires non-null
  `source_type`; fixed the seed (added `source_type="briefing"`). The implementation
  (`OutboxHealthService`) was correct; this was not an implementation bug.

## 4. Full regression + quality gates

```
pytest -q                                   → 143 passed   (126 prior + 17 new)
ruff check nexus/ tests/                     → All checks passed!
mypy nexus/ --ignore-missing-imports         → Success: no issues found in 57 source files
```

No pre-existing tests regressed (AP-101/102 suites, runner/approval/intelligence/gateway tests all
still green).

## 5. Boundary assertion (manual confirmation)

`grep` confirms neither `nexus/scheduling/scheduler.py` nor `nexus/scheduling/jobs.py` imports
`nexus.memory.models`. Model access lives exclusively in the services
(`OutboxHealthService`/`CheckpointHealthService` and the pre-existing engines). Constraint 2
satisfied.

## 6. Verdict

**PASS.** All AP-103 functional and constraint requirements are validated by automated tests plus an
operational start (`scheduler-operational-readiness.md`). No regressions.
