# Validation Matrix

Every operational claim traced end-to-end: **Capability → Validation Method → Evidence → Report → Release.**
Each row lets a reader start from a capability they care about and follow it to the exact test(s) and
report section that back it, rather than taking the claim on faith.

| Capability | Validation method | Evidence | Report | Release |
|---|---|---|---|---|
| Event-sourced persistence (event log authoritative; state/checkpoints are projections) | Replay-equivalence test; recover-and-resume test | `test_pipeline_replays_from_the_durable_log`; durable/in-memory event throughput benchmark | ADR-001 §8; `RC1_PRODUCTIZATION_REPORT.md` §6.2 | v2.0.0 |
| Deterministic replay across concurrent goals | Two-goal replay reconstruction test | `test_replay_after_two_concurrent_goals_reconstructs_each_independently` | `RC2_EXECUTION_IDENTITY_REPORT.md` §5 | v2.0.0 |
| Restart resumes from last completed stage, never re-runs or adopts foreign state | Restart/interruption regression suite | `test_pipeline_restarts_from_the_last_completed_stage`, `test_pipeline_restarts_after_a_mid_execution_interruption`, `test_restart_never_double_dispatches` | `RC2_EXECUTION_IDENTITY_REPORT.md` §6; `RC1_PRODUCTIZATION_REPORT.md` §2.3 | v2.0.0 |
| Scheduler dispatch (one-time, recurring, delayed) | Full scheduler integration suite | `tests/integration/test_scheduler.py` (7 tests) | `V1_RELEASE_READINESS_REPORT.md` §4 | v2.0.0 |
| Scheduler `tick()` scales linearly with registered schedules | Scale benchmark, 10→2000 schedules | `scripts/p17_scale.py` output | `RC1_PRODUCTIZATION_REPORT.md` §3, §6.1 | v2.0.0 |
| Recurring schedule occurrences each run their own goal (not a reused one) | Multi-occurrence replay test | `test_recurring_schedule_occurrences_each_run_their_own_goal` | `RC2_EXECUTION_IDENTITY_REPORT.md` §5, §7 | v2.0.0 |
| Cross-goal execution isolation (Runtime Session / Validation scope) | Two-goal collision reproduction + regression tests | `test_two_goals_with_identical_work_item_keys_do_not_collide`, `test_two_goals_sharing_a_node_key_do_not_cross_contaminate_scopes`, dispatch unit tests | `RC2_EXECUTION_IDENTITY_REPORT.md` §7 | v2.0.0 |
| Policy Engine — fail-closed default, deterministic conflict resolution | Fail-closed test; conflict-resolution truth table | ADR-004 §8's specified test set; `examples/03-policy-governance/` | ADR-004 §3.1, §8 | v2.0.0 |
| Policy registry restart-safety | Restart regression test (real, advancing clock) | The defect reproduction and fix in `nexus_policy/composition.py`/`registry.py` | `RC1_PRODUCTIZATION_REPORT.md` §2.3 | v2.0.0 |
| Runtime Manager restart/re-actuation-safety | Two-actuation-call reproduction over one durable infra | Commit `fix(runtime): make register_runtime restart/re-actuation-safe under a real clock` | `RC1_PRODUCTIZATION_REPORT.md` §2.5 | v2.0.0 |
| Approval Exchange — gate lifecycle, session integrity | Full approval integration suite | `tests/integration/test_approval_exchange.py` (5 tests) | `V1_RELEASE_READINESS_REPORT.md` §4 | v2.0.0 |
| Governed autonomy (`AutonomyMode` tiers never bypass Policy) | Policy-controlled auto-approval test | `test_policy_controlled_auto_approval` | `RC2_EXECUTION_IDENTITY_REPORT.md` §7 | v2.0.0 |
| Production entrypoint boots the full durable spine and dispatches a real goal | Bootstrap + single-tick dispatch integration test; direct manual smoke test | `tests/integration/test_v2_entrypoint.py` (4 tests); `python -m nexus_scheduler --db <tmp> --once` | `RC1_PRODUCTIZATION_REPORT.md` §2.4 | v2.0.0 |
| No forbidden cross-package dependencies (architecture-fitness) | Dependency-boundary guardrail tests | `tests/unit/nexus_scheduler/test_guardrails.py::test_scheduler_reaches_no_engine` (caught a real first-draft violation) | `RC1_PRODUCTIZATION_REPORT.md` §2.2 | v2.0.0 |
| Type safety across the v2 surface | `mypy --strict`, full v2 scope | 388 source files, 0 errors (final) | `V2_RELEASE_EXECUTION_REPORT.md` §4 | v2.0.0 |
| Lint and format cleanliness | `ruff check` + `ruff format --check` | Clean, repository-wide; 696 files (format check) | `V2_RELEASE_EXECUTION_REPORT.md` §4 | v2.0.0 |
| Full regression suite passes with zero failures | `pytest tests/` | 3215 passed, 1 unrelated opt-in skip, 0 failed (final) | `V2_RELEASE_EXECUTION_REPORT.md` §4 | v2.0.0 |
| Packaging integrity (all 31 v2 packages + v1 ship in one wheel) | Wheel build + artifact inspection | `nexus-2.0.0-py3-none-any.whl`, 31/31 packages present | `V2_RELEASE_EXECUTION_REPORT.md` §4 | v2.0.0 |
| CI green on the actual tagged commit | GitHub Actions, all required jobs | 5/5 jobs passed on merge commit `07097ac` | `V2_RELEASE_EXECUTION_REPORT.md` §2, §4 | v2.0.0 |
| Version consistency (single source of truth across 31 packages + `pyproject.toml`) | Per-package `__version__` audit | All 31 `nexus_*/__init__.py` + `pyproject.toml` read `2.0.0`, individually verified | `V2_RELEASE_EXECUTION_REPORT.md` §5 | v2.0.0 |
| ADR-009 (Runtime Selection Ownership) ships honestly disclosed as unratified | Cross-reference check across CHANGELOG, ADR index, release report | `adr/README.md`; `CHANGELOG.md` [2.0.0]; `ADR_RATIFICATION_REPORT.md` | `V2_RELEASE_EXECUTION_REPORT.md` §6 | v2.0.0 |

**How to read a row you don't recognize:** every "Report" cell is a real section in a released document
under `docs/v2/`; every "Evidence" cell names a real, runnable test or script — none is paraphrased or
invented for this matrix. Where a capability's validation has a known boundary, that boundary is documented
in [`guarantees.md`](guarantees.md), not silently omitted here.
