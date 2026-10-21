# Operational Guarantees

Each guarantee below links to (1) the implementation that provides it, (2) the validation that checked it,
and (3) the report that recorded the result. Every guarantee is stated at the strength the evidence actually
supports — where a guarantee has a known boundary or a disclosed exception, that boundary is stated in the
same entry, not left implicit.

## Deterministic replay

**Guarantee:** folding the same event stream twice produces identical state; replaying an operation
reproduces its governed outcome without re-invoking any model.

- **Implementation:** `nexus_core/persistence/interfaces.py` (event store contract); `nexus_workflows/spine/coordinator.py`'s `reconstruct_pipeline_session` — a pure function over `(events, session_id)`.
- **Validation:** `test_pipeline_replays_from_the_durable_log` (pre-existing, still passes unchanged after RC2); RC2's own `test_replay_after_two_concurrent_goals_reconstructs_each_independently` (proves replay is correct even when two goals share one durable log — the specific case a pre-RC2 platform would have gotten wrong, per `RC2_EXECUTION_IDENTITY_REPORT.md` §2.3).
- **Report:** `docs/v2/RC2_EXECUTION_IDENTITY_REPORT.md` §5 (Replay Validation); `docs/v2/RC1_PRODUCTIZATION_REPORT.md` §6.2 (replay throughput, 170,989 events/sec at 2,200 events; 92,742 events/sec at 20,000 events).
- **Boundary, stated honestly:** this guarantee held for the single-goal case even *before* RC2 — the multi-goal case was a real, reproduced gap (RC1's risk #12) that RC2 closed. A reader relying on this guarantee against a version of the platform predating RC2's fixes (commits `cbd3177`/`4af2ffb`) would not actually have it for concurrent goals.

## Restart correctness

**Guarantee:** a process interrupted mid-execution and restarted against the same durable file resumes from
its last completed stage, never re-running completed work and never adopting another goal's state.

- **Implementation:** `ConstitutionalPipeline._seed` (`nexus_workflows/spine/coordinator.py`) — now matches reconstructed artifacts against the request's own goal-reference field (`Plan.parent_goal`, `ExecutionState.goal_ref`, `EngineeringStrategy.subject_identifier`), not "first fact of this type in the log."
- **Validation:** `test_pipeline_restarts_from_the_last_completed_stage`, `test_pipeline_restarts_after_a_mid_execution_interruption`, `test_restart_never_double_dispatches` (pre-existing, pass unchanged); RC2's `test_recurring_schedule_occurrences_each_run_their_own_goal` (proves three occurrences of one recurring schedule each get their own Intent→Knowledge run, not one reused run — the exact failure mode Defect C's *first* attempted fix would have reintroduced, per `RC2_EXECUTION_IDENTITY_REPORT.md` §2.3).
- **Report:** `docs/v2/RC2_EXECUTION_IDENTITY_REPORT.md` §6 (Restart Validation); `docs/v2/RC1_PRODUCTIZATION_REPORT.md` §2.3 (the restart-safety defect found and fixed in Policy composition — a narrower, earlier instance of the same class of bug).
- **Boundary, stated honestly:** RC2's own §9 discloses a *dormant*, unfixed risk one layer away — `ConstitutionalPipeline.execution_graph()`/`execution_state()` (read-only inspection methods) still resolve unfiltered by goal identity; this cannot corrupt the durable log (it is a read path) but can return the wrong goal's projection to a caller inspecting state after multiple goals ran on one coordinator. Not a restart-correctness violation; a read-path ambiguity, disclosed as a fast-follow.

## Policy enforcement (fail-closed)

**Guarantee:** an action with no matching policy is denied, not allowed through; policy evaluation is
deterministic (identical request + policies → identical decision, every run).

- **Implementation:** `nexus_policy` — the Default Policy (deny-by-default for governed actions), specificity → priority → version → default conflict resolution (ADR-004 §3.1).
- **Validation:** the fail-closed test and conflict-resolution truth table ADR-004 §8 specifies (`AP-406`); `examples/03-policy-governance/` demonstrates the fail-closed default directly against a real `DecisionRequest`/`GLOBAL_COMMAND_BLACKLIST` match.
- **Report:** ADR-004 itself (the ratifying decision); `docs/v2/ARCHITECTURE_CONSTITUTION.md`'s COORDINATE step (the Constitution's own restatement).
- **Boundary, stated honestly:** RC1's own §2.3 found and fixed a real restart-safety defect specifically in Policy's own composition root (`build_policy` unconditionally re-seeding baseline policies on every restart, crashing under a real advancing clock) — fail-closed evaluation itself was never wrong, but the registry that holds policies to evaluate against had a real, now-fixed, restart bug.

## Approval integrity

**Guarantee:** a gated node pauses execution until an explicit human decision (`approve`/`deny`), and that
decision is recorded durably against the exact pipeline session and content it applies to.

- **Implementation:** `nexus_approval.ApprovalExchange` (`publish`/`approve`/`deny`/`expire`/`session`/`pending`/`history`/`explanation`); session identity is `pipeline_session_id` + content-hash-hardened (confirmed via file:line trace in `RC2_EXECUTION_IDENTITY_REPORT.md` §3's identity-model audit — not touched by any of RC2's three defects because it was already correctly scoped).
- **Validation:** `tests/integration/test_approval_exchange.py` (5 tests, all pass); `test_approval_required_execution_is_surfaced_then_completed` (exercises approval against a goal dispatched through the Scheduler, not just directly); `examples/07-approval-exchange/` demonstrates the full Requested→Pending→Approved lifecycle against real APIs.
- **Report:** `docs/v2/V1_RELEASE_READINESS_REPORT.md` §4 (Approval validation: full suite, 5 tests, pass).
- **Boundary, stated honestly:** no bespoke concurrent-approval regression test was added during RC1/RC2 specifically — the guarantee's correctness under concurrent multi-goal execution rests on Approval's identity scheme already being correct (verified by trace, not by a new adversarial test built for this exact scenario), per `RC2_EXECUTION_IDENTITY_REPORT.md` §7's own explicit statement of this.

## Scheduler determinism

**Guarantee:** dispatch decisions (which schedules fire, in what order, exhausted or not) are a pure
function of the durable event log and the injected clock — never a wall clock read directly inside the
platform, never dependent on process memory surviving a restart.

- **Implementation:** `Scheduler.tick(now)` — every call takes `now` as an explicit parameter; `nexus_scheduler`'s own `system_now` adapter is the only clock source, and only the entrypoint (`nexus_scheduler/__main__.py`) ever calls the real wall clock.
- **Validation:** `tests/integration/test_scheduler.py` (7 tests, including RC2's new `test_recurring_schedule_occurrences_each_run_their_own_goal`); the architecture-fitness test `test_scheduler_reaches_no_engine` (`tests/unit/nexus_scheduler/test_guardrails.py`) — enforces that `nexus_scheduler` cannot depend on `nexus_runtime` directly, keeping its dispatch decisions free of execution-layer nondeterminism.
- **Report:** `docs/v2/RC1_PRODUCTIZATION_REPORT.md` §2.2 (the guardrail catching a real first-draft violation during entrypoint construction — the boundary held under real construction pressure, not just in theory); `docs/v2/V1_RELEASE_READINESS_REPORT.md` §4 (Scheduler validation: full suite, 7 tests, pass).
- **Boundary, stated honestly:** determinism here means *the Scheduler's own decision process* is deterministic given its inputs — it does not mean two runs against a real, differently-advancing wall clock produce byte-identical timestamps in the log. The guarantee is about decision logic, not clock value reproducibility.

## Execution isolation (cross-goal)

**Guarantee:** two goals sharing one durable log execute independently — neither can adopt the other's
state, corrupt the other's event scope, or silently short-circuit its own execution because of the other's
presence.

- **Implementation:** the three RC2 fixes — `nexus_execution/actuation/dispatch.py` (Runtime Session identity now goal-scoped, not work-item-key-scoped), `nexus_workflows/spine/bridge.py` (Execution→Validation scope lookup filtered to the current execution session), `nexus_workflows/spine/coordinator.py` (restart-seeding matched to the request's own goal identity).
- **Validation:** `test_two_goals_with_identical_work_item_keys_do_not_collide`, `test_two_goals_sharing_a_node_key_do_not_cross_contaminate_scopes`, `test_package_identity_is_scoped_by_session_not_node_alone`, `test_package_identity_is_deterministic_for_the_same_session_and_node` — all new, all built specifically to reproduce and then disprove the original defects.
- **Report:** `docs/v2/RC2_EXECUTION_IDENTITY_REPORT.md` §7 (Concurrency Validation) in full — this is the guarantee the entire RC2 report exists to establish.
- **Boundary, stated honestly:** this is the guarantee with the most disclosed remaining risk of any in this
  list. `RC2_EXECUTION_IDENTITY_REPORT.md` §9 names four items *not* fixed: `GraphNode.identifier` and its
  checkpoint reference remain pure functions of the work-item key alone (latent — safe only because every
  current consumer looks them up inside an already goal-scoped container; a future consumer that doesn't
  would reproduce Defect A's exact shape); two read-path methods (`execution_graph()`/`execution_state()`)
  still resolve unfiltered (dormant, read-only, cannot corrupt data); Recovery is invoked with
  `checkpoint_ref=None` unconditionally (an independent, unrelated INV-18 gap noticed in passing). None of
  these are corruption paths in currently-exercised code — but this is the one guarantee in this document
  where "fixed" means "the three reproduced defects are fixed," not "every theoretical variant of this
  defect class is closed."

## Deterministic scale ceiling removed (Scheduler linear, not quadratic)

**Guarantee:** `Scheduler.tick()` cost grows linearly, not quadratically, with the number of registered
schedules — the platform will not silently become too slow to dispatch under normal autonomous growth.

- **Implementation:** `nexus_scheduler/scheduler.py`'s `_maybe_complete` (no longer re-fetches/re-reconstructs schedule history per call).
- **Validation:** `scripts/p17_scale.py`, re-run at RC1 — see [`scheduler.md`](scheduler.md) for the full before/after table.
- **Report:** `docs/v2/RC1_PRODUCTIZATION_REPORT.md` §3, §6.1.
- **Boundary, stated honestly:** verified up to 2,000 registered schedules only; see
  [`README.md`](README.md#what-nexus-has-not-benchmarked)'s "million-job scheduling" entry.
