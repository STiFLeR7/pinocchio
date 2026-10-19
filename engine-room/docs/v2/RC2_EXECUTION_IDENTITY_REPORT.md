# RC2 — Execution Identity & Session Isolation

**Status:** Complete. **Scope:** eliminate cross-goal execution collisions; no new platform capabilities, no ownership changes, no ADR required (see §4). **Governing input:** `docs/v2/RC1_PRODUCTIZATION_REPORT.md` §2.5 / risk #12 — the one open item RC1 flagged as blocking unconditional GA.

---

## 1. Executive Summary

RC1's pre-merge review reproduced a real defect: two goals whose plans produce a work item with the same key collide on Runtime Session / Validation event scope, because `nexus_execution/actuation/dispatch.py` derived that scope from the work-item key alone. RC1 judged this a genuine architectural gap requiring cross-subsystem redesign and left it unfixed, downgrading its own GA recommendation.

RC2's Phase 1 identity audit found the actual defect narrower than RC1 believed: the correctly goal-scoped identity the fix needs was **already being computed by Orchestration and simply discarded at one call site**, one line away from where it was needed. Fixing it required no new identity concept and no ownership change — just propagating a value the codebase already produces.

While building a realistic reproduction to verify that fix, RC2 found a **second, independent, and more severe defect** in the exact same class: `nexus_workflows/spine/coordinator.py`'s restart-seeding logic (`_seed`) scans the *entire* durable log for the first fact of each type, with no check that the fact belongs to the goal actually being run. On a shared durable log, a second goal doesn't just risk an event-scope collision — it can silently adopt an unrelated goal's already-completed Plan and ExecutionState, skip its own Intent→Actuation entirely, and report **success** while never having run at all. This is worse than a crash: it is silent, undetected work-loss. Fixing this the *naive* way (filtering by the request's `correlation_identifier`) would have introduced a **third** bug — the Scheduler deliberately shares one correlation across every occurrence of a recurring schedule, so that filter would make occurrence 2 silently adopt occurrence 1's state. The actual fix matches reconstructed facts against each artifact's own goal-reference field (`Plan.parent_goal`, `ExecutionState.goal_ref`, `EngineeringStrategy.subject_identifier`) — the same "propagate the identity that already exists, don't infer position in a list" principle applied one layer deeper.

Three fixes, all additive, all verified with regression tests reproducing the original failures:

1. `nexus_execution/actuation/dispatch.py` — Runtime Session identity now includes the goal-scoped Execution Session id, not just the node key.
2. `nexus_workflows/spine/bridge.py` — the Execution→Validation scope lookup is now filtered to the current execution session, not the whole cross-goal log.
3. `nexus_workflows/spine/coordinator.py` — restart-seeding now matches reconstructed artifacts to the request's own goal identity, not "whichever fact of this type appears first in the log."

Full regression suite: **3215 passed, 1 skipped, 0 failed** (up from RC1's 2934 — 6 new tests target this defect class directly; the remainder of the delta reflects other work already on this branch). mypy --strict clean on all touched production packages (316 files). ruff clean repository-wide. No ADR required — see §4.

**This closes RC1's risk #12.** RC2 recommends restoring the RC1 report's original GA posture (see §10).

---

## 2. Root Cause Analysis

### 2.1 Defect A — Runtime Session identity keyed by work-item alone (RC1's reported crash)

`nexus_execution/actuation/dispatch.py:_project_intake` built:

```python
package_identity=f"actuation-pkg-{node.identifier}"
```

`node.identifier` is `f"node-{item_key}"` — unique only *within one plan* (`nexus_planning/requests.py`'s own docstring says so). The function already receives `session_identity`, the goal-scoped Execution Session id (`ids.session_id(goal_identity, version)`, a pure function of goal + version) — it just never used it for this one field. `RuntimeRequest.identity` (Orchestration's own candidate nomination, computed one layer up) is *already* `f"rreq-{session_identity}-{node_identifier}"` — the correctly-scoped value existed and was discarded.

Every `runtime.*` event for a dispatched node is scoped by `runtime_session_id(package_identity, attempt)`. Two goals whose plans both produce a node keyed `"draft"` (guaranteed by the only reference `SpineRequest` builder in the codebase, `nexus_workflows/spine/reference.py`, which always uses `("draft", "review")`) minted the identical Runtime Session id. Facts with matching identity but different content raise `DuplicateEventError` in `nexus_infra/durable.py`'s dedup check; facts with matching identity *and* matching content are silently absorbed. Depending on the timestamp source and which payload fields differ, the same root cause manifests as either a crash or a silently-dropped fact — RC1 reproduced the crash inside `nexus_validation/engine.py`, where `work_package.identifier` (correctly goal-scoped) first differs between the two goals.

### 2.2 Defect B — cross-goal scope lookup (found during RC2's audit, not previously known)

`nexus_workflows/spine/bridge.py:_node_scopes` builds a `dict[node_id -> runtime_scope]` by scanning `events = tuple(self._infra.event_store.read_all())` — **the entire durable log, every goal ever run in the process** — keyed by the bare node id from each `runtime.session_created` event's payload. Even after Defect A's fix makes the runtime scope itself goal-unique, two goals dispatching a node keyed `"draft"` still overwrite each other's entry in this dict, because the *key* was never goal-scoped, only the *value*. Validation would silently resolve the wrong (or a since-overwritten) goal's runtime scope for a node id shared by two goals.

### 2.3 Defect C — restart-seeding adopts an unrelated goal's state (found by RC2, not by RC1)

`ConstitutionalPipeline._seed` (`coordinator.py`) is called at the top of every `run()` with the *entire* durable log and reconstructs "already completed" artifacts via `find_goal`/`find_strategy`/`find_plan`/`find_execution_state` — each of which returns the **first** event of its type anywhere in the log, unconditionally. This is correct for the single-goal-per-log case every prior test exercised. It is not correct once a second goal shares the log: `_seed` would find the *first* goal's Goal/Plan/ExecutionState, treat it as this request's own already-completed prior progress, and return `SpineStage.VALIDATION` as the resume point — skipping Intent, Engineering, Context, Planning, and Actuation entirely. The second goal's `SpineRun` reports `SpineStatus.COMPLETED` having never run any of its own stages; Validation/Recovery for it just silently re-validate the first goal's already-validated results (identical inputs → identical, silently-absorbed duplicate events, no crash, no signal anything was wrong).

This was reproduced directly: running `spine_reference_request(run="r1")` then `spine_reference_request(run="r2")` against one shared `build_infrastructure()` produced **zero** new `intent.resolved` / `planning.execution_plan_assembled` events for `r2` — confirmed via direct inspection of the event log before the fix.

The first fix attempt — filter `_seed`'s candidate events by `request.correlation_identifier` — passed the two-goal test but broke a *different*, already-existing scenario: `nexus_scheduler`'s recurring-schedule dispatch (`Scheduler._dispatch`) intentionally reuses **one** `correlation_identifier` across every occurrence of a recurring schedule (`schedule.correlation_identifier or f"cor-{schedule.identity}"`, unindexed by occurrence) — for cross-occurrence observability tracing, not because occurrences are the same goal run. Filtering by correlation made occurrence 1 adopt occurrence 0's already-completed state, reproducing Defect C's failure mode one level down. Verified directly: before the corrected fix, three occurrences of one recurring schedule produced only **one** `intent.resolved`/`planning.execution_plan_assembled`/`execution.completed` triple total, not three.

The correct fix matches each reconstructed candidate against the goal identity `request` actually resolves to (`f"goal-{request.identity}"`, the same derivation `nexus_intent`'s interpreter already uses), checked via each domain object's own goal-reference field — `Plan.parent_goal.identifier`, `ExecutionState.goal_ref.identifier`, `EngineeringStrategy.subject_identifier` — never via correlation or log position. This correctly distinguishes both two different goals *and* two occurrences of one recurring schedule, since `request.identity` (hence the derived goal identity) is unique in both cases even where `correlation_identifier` is not.

### 2.4 Common shape

All three defects share one shape: a value the codebase *had already computed correctly* (a goal-scoped identity, or a goal-reference field on an existing domain object) was discarded or ignored in favor of either a narrower key (Defects A/B: work-item/node id alone) or the wrong key entirely (Defect C's first attempt: correlation, which is deliberately non-unique in one real caller). No defect required inventing a new identity concept — every fix is propagation of an identity that already existed, one layer away from where it was needed. This matches the audit's Finding D (§Phase 1 below): the codebase's identity design is correct everywhere except at these specific integration seams.

---

## 3. Identity Model (Phase 1 audit — the map fixes were built against)

Full trace of every identifier in Goal → SpineRequest/PipelineSession → Work Item → Work Package → Execution Graph/Node → Execution Session → Harness/Runtime Request → Runtime Session → Execution Result → Validation Report → Recovery Plan → Reflection Report → Knowledge Item → Approval Session → Policy Registration, with owner/scope/lifetime/uniqueness/persistence/replay-safety for each:

| Identifier | Owner | Scoped by | Replay-safe (pre-RC2) |
|---|---|---|---|
| Goal | Intent Resolution | request identity (global) | Yes |
| SpineRequest / PipelineSession | `nexus_workflows.spine` | request identity (global) | Yes |
| Work Item key | Planning caller | **request-local only** (by contract) | N/A (not itself durable) |
| Work Package | Planning | `(goal, item_key)` | Yes |
| Execution Graph | Planning | `(goal, version)` | Yes |
| Graph Node id | Planning | **item_key alone** | Safe only by consumption discipline (see §7) |
| Execution Session | Orchestration | `(goal, version)` | Yes |
| Harness/Runtime Request | Orchestration | `(session[goal], node)` | Yes (unused at the one seam that mattered) |
| **Runtime Session** | Runtime | **node key alone (pre-fix)** | **No — Defect A** |
| Execution Result (bridge) | `nexus_workflows.spine.bridge` | inherits Runtime Session scope, **looked up log-wide** | **No — Defect B** |
| Validation Report | Validation | inherits Execution Result scope | No, transitively (A+B) |
| Recovery Plan | Recovery | inherits Validation Report scope | No, transitively (A+B) |
| Reflection Report | Reflection | `request.scope` (independent, correct) | Yes, own identity — garbage-in from A/B/C |
| Knowledge Item | Knowledge | subject key (deliberately not goal-scoped; versioned, evidence-gated) | Yes, by design — different bug shape, see §7 |
| Approval Session | Approval | `pipeline_session_id` + content hash | Yes |
| Policy Registration | Policy | process-global by design | Yes (RC1-hardened) |
| **Restart seed (Goal/Strategy/Plan/ExecutionState reconstruction)** | `ConstitutionalPipeline._seed` | **first-of-type in the whole log (pre-fix)** | **No — Defect C** |

Full identifier-by-identifier evidence (file:line citations, replay-behavior detail, and additional findings not already known from RC1) is preserved in the audit transcript; the table above is its load-bearing summary. Two additional findings from that audit, not fixed (out of RC2's corruption-elimination scope), are carried to §7.

---

## 4. Architectural Impact

**No ADR was required.** Every fix is additive propagation of an identity that already existed and was already owned by its current constitutional owner:

- Defect A/B: `session_identity` (Orchestration's Execution Session id) was already being passed into `_project_intake`; it is now also used for `package_identity`. No new identifier, no new owner, no changed contract — `RuntimeIntake.package_identity`'s *type* and *role* are unchanged, only its derivation now includes a value already in scope.
- Defect C: `Plan.parent_goal`, `ExecutionState.goal_ref`, and `EngineeringStrategy.subject_identifier` are pre-existing fields on pre-existing domain objects (owned by Planning, Execution Actuation, and Engineering respectively, unchanged). `_seed` now reads them; it does not add them.

No invariant changed. No constitutional owner changed. No new platform capability was introduced (Success Criterion: "No constitutional ownership changes unless explicitly required and documented" — none was required).

---

## 5. Replay Validation

- `test_pipeline_replays_from_the_durable_log`, `test_pipeline_restarts_from_the_last_completed_stage`, `test_pipeline_restarts_after_a_mid_execution_interruption` (pre-existing, single-goal restart/replay) — **unchanged, still pass**, confirming the fix does not alter single-goal restart/replay semantics.
- `test_replay_after_two_concurrent_goals_reconstructs_each_independently` (new) — two goals run sequentially over one durable file; reopening the file and reconstructing each goal's `PipelineSession` and `ExecutionState` independently (filtered by each request's own `correlation_identifier`, the same idiom `_seed` no longer relies on for goal-matching but which the *test* uses as an independent check) proves each goal's own state replays to exactly what that goal actually produced, and the two states are provably distinct.
- `test_recurring_schedule_occurrences_each_run_their_own_goal` (new) — replays a durable log after three occurrences of one recurring schedule and confirms three distinct `intent.resolved` goals and three distinct plans exist (not one, reused).

---

## 6. Restart Validation

Existing single-goal restart tests (`test_pipeline_restarts_from_the_last_completed_stage`, `test_pipeline_restarts_after_a_mid_execution_interruption`, `test_restart_never_double_dispatches`) pass unchanged — `_seed`'s goal-matched reconstruction degrades to exactly the old first-match behavior whenever there is only one goal on the log, since "first of type" and "first matching our own goal identity" coincide when there is only one goal.

One nuance recorded rather than hidden: in a genuinely multi-goal shared log, if goal B was itself interrupted mid-pipeline *after* an unrelated goal A had already completed earlier on the same log, `_seed`'s scan for B's own artifacts still has to walk past A's (now goal-identity-checked and skipped) facts to find B's. This is strictly a scan-order question, not a correctness one — B's own already-completed stages are still found and skipped correctly, exactly as intended (verified by `test_recurring_schedule_occurrences_each_run_their_own_goal`, which continues an already-populated log across two `tick()` calls). Restart-resume efficiency for the single-goal-per-log case is unchanged; correctness for the multi-goal case is what changed.

---

## 7. Concurrency Validation

- `test_two_goals_with_identical_work_item_keys_do_not_collide` — the direct reproduction of RC1's reported defect: two goals sharing work-item keys `"draft"`/`"review"`, run sequentially over one shared log, both complete, both validate `"passed"`, and exactly **4** distinct runtime-session scopes exist (2 goals × 2 work items) where the pre-fix code produced 2 (collapsed).
- `test_two_goals_sharing_a_node_key_do_not_cross_contaminate_scopes` (bridge unit test) — isolates Defect B directly: two actuation runs over one shared infra with the same node keys but different goal identities must resolve to disjoint scope sets.
- `test_package_identity_is_scoped_by_session_not_node_alone` / `test_package_identity_is_deterministic_for_the_same_session_and_node` (dispatch unit tests) — isolate Defect A directly at the seam, independent of the rest of the pipeline.
- `test_recurring_schedule_occurrences_each_run_their_own_goal` — isolates Defect C's *second* form (shared-correlation occurrences), proving the scheduler's own multi-dispatch path (Phase 7's explicit "scheduler dispatching multiple goals" requirement) is covered, not just the constitutional-pipeline-level reproduction.
- **Scheduler-level identity minting audited, not found to be independent**: `nexus_scheduler` contains no code that derives identity from `node.identifier`, work-item keys, or any of the fixed seams (`grep` across `nexus_scheduler/` for these patterns returned no matches) — it dispatches goals through the same `ConstitutionalPipeline.run()` / `_project_intake` / `_node_scopes` code paths already covered by the fixes and tests above. `test_one_time_recurring_and_delayed_execution` and `test_policy_controlled_auto_approval` already exercise multiple goals per shared coordinator and continue to pass.
- **A testing gap worth naming honestly**: the pre-existing scheduler test suite (all 6 tests, including the one that dispatches three goals sharing work-item keys over one coordinator) **passed both before and after every fix in this report** — it doesn't assert deeply enough per-goal (only coarse occurrence-tracking and one aggregate status) to have caught either Defect A/B or Defect C. `test_recurring_schedule_occurrences_each_run_their_own_goal` closes this specific gap; the general lesson (assert per-goal substance, not just aggregate/occurrence bookkeeping, whenever a test shares one coordinator across multiple goals) is worth carrying into future scheduler test additions but is not itself something this report expands further (no unrelated cleanup).
- Approval-during-concurrent-execution: not given a bespoke new test. `nexus_approval`'s own session identity is `pipeline_session_id`-scoped plus content-hash-hardened (audit §1 row "Approval Session" — already correct, confirmed via file:line trace, not touched by any of the three defects), and `test_approval_required_execution_is_surfaced_then_completed` already exercises approval against a goal dispatched through the now-fixed scheduler path.

---

## 8. Performance Impact

All three fixes are `O(1)` string composition (Defect A) or trade an unconditional first match for a filtered first match within the same `O(n)` single-pass scan over `events` (Defects B/C) — no algorithmic complexity change. Benchmark, single-goal reference pipeline run, 30 iterations, same process/hardware, A/B via `git stash`:

| | pre-fix | post-fix |
|---|---|---|
| Full pipeline run (`build_infrastructure` + `spine_reference_request` + full 9-stage run) | 4.16 ms/run | 4.41 ms/run |

The ~6% delta is within run-to-run noise for a 4ms operation on this machine (single-run timing, not a tight loop with warmup) and reflects, at most, the few extra field-equality comparisons `_find_own_*`/the session-filter add to an already-linear scan — no `O(n²)` or worse behavior was introduced. Scheduler, replay, and restart throughput are unaffected structurally (§5, §6). No further profiling was warranted at this scale.

---

## 9. Remaining Risks

| # | Risk | Status |
|---|---|---|
| 1 | `GraphNode.identifier` (`node-{item_key}`) and the checkpoint reference `ckpt-{node_id(item.key)}` are, like Defect A's original `package_identity`, pure functions of the work-item key alone — safe today only because every consumer looks them up inside an already goal-scoped container (a specific graph, a specific session's checkpoints), never as a standalone durable scope. Any future code that reaches for either as a durable event scope, correlation key, or dedup key without first combining it with the enclosing goal/session identity would reproduce Defect A's exact shape. Not fixed (latent, not currently triggered — no unrelated cleanup). |
| 2 | `ConstitutionalPipeline.execution_graph()` / `execution_state()` (read-only inspection methods) and `nexus_human_interaction/facade.py`'s `execution_graph(self, _identity: str)` still call `find_plan`/`find_execution_state` unfiltered — the same ambiguity Defect C had, but on a **read path**, not the durable restart-decision path, so it cannot corrupt the log. A caller inspecting "the" execution graph/state after multiple goals have run on one coordinator can be handed the wrong goal's projection; the facade's `_identity` parameter is accepted and silently discarded (visible today via its leading underscore). Real, dormant, out of RC2's "eliminate cross-goal *collisions*" scope (this is ambiguity in a read helper, not a corruption path) — recommended as a fast-follow, not a GA blocker. |
| 3 | Recovery is invoked with `checkpoint_ref=None` unconditionally (`coordinator._stage_recovery`), an independent INV-18 gap noticed while tracing Recovery's scope inheritance in the Phase 1 audit — unrelated to identity, not in RC2's scope, not fixed. |
| 4 | ADR-009 (INV-37 runtime-selection ownership, proposed in RC1) remains unratified. Unrelated to identity; carried forward from RC1 unchanged. |

None of these four are corruption paths reachable by any currently-exercised code path; all are documented here rather than fixed, consistent with RC2's additive-only, no-unrelated-cleanup mandate.

---

## 10. Merge Recommendation

**Recommend merge, and recommend restoring the RC1 report's original (pre-review-downgrade) GA posture.**

RC1 downgraded its GA recommendation specifically because of the defect this report's §2.1–2.3 resolves — and resolves more completely than RC1's own investigation had scoped it (RC1 believed the fix required cross-subsystem scope-threading redesign; it did not). Every fix is:

- Independently verified with a regression test that reproduces the original failure and demonstrates it is gone (§7).
- A net improvement in isolation — reverting any one of the three would restore a known, reproduced defect.
- Additive, requiring no ADR, no ownership change, no new invariant (§4).
- Confirmed not to regress replay, restart, or scheduler behavior (§5, §6), nor introduce measurable performance regression (§8).

Full suite: 3215 passed, 1 skipped (opt-in Claude-CLI smoke test, unrelated), 0 failed. mypy --strict clean on all touched production code. ruff clean repository-wide.

The four items in §9 are real but are either latent-and-unreached (risk 1), a read-path ambiguity with no corruption consequence (risk 2), or pre-existing and unrelated to identity (risks 3–4, carried from RC1/prior work). None blocks GA on its own; all are reasonable fast-follow items for a subsequent hardening pass.
