# H-4 — Nexus Pilot Upgrade: Implementation Summary & Required Output

> **Release line:** v1.1.0 "Containment" · **AP:** H-4 · **Track:** H · **Status:** ✅ Complete (all 7
> P1 steps) · **Method:** strict TDD (RED→GREEN→regression per step) + systematic-debugging discipline.
> Branch `v1.1.0-planning`, on H-2 freeze `d6bd75d`. **No commit, no tag, no maturity-doc update** —
> awaiting review. Per-step reports: `H-4.1`…`H-4.7-*.md`.

---

## 1. Exact files modified

| File | Type | Change |
|---|---|---|
| `nexus/execution/runners/nexus.py` | modify (+213/-…) | fail-fast `initialize()`; `_max_steps()`; cooperative `terminate()` + `_is_cancelled()` (in-process + DB-observable) + `_record_terminal_marker()`; `_active_process` tracking in `execute_command`; `_run_loop()` extraction; cancellation + wall-clock/budget `TIMED_OUT` terminals; honest cancelled/timed_out/failed/completed status; `resume_goal()` |
| `nexus/scheduling/orchestrator.py` | modify (+25) | `resolve_exit_status(result)` (status→ExitStatus, exit_code fallback); finalize uses it (the **single** orchestrator touch) |
| `nexus/config.py` | modify (+2) | additive `ExecutionConfig.agent_max_steps: int = 5` |
| `tests/unit/execution/test_nexus.py` | modify (+8/-…) | migrated `test_nexus_initialize` to injected client (fail-fast) |
| `tests/unit/execution/test_nexus_lifecycle.py` | **new** | 19 H-4 lifecycle tests + injected fakes |

**No schema changes, no migrations.** `ExecutionStatus.TIMED_OUT`/`CANCELLED` and `ExitStatus.TIMEOUT`/
`CANCELLED` already existed; the cancel signal reuses the existing nullable `ExecutionRecord.exit_status`.

## 2. Total tests before and after

| Point | Total |
|---|---|
| Before H-4 (H-2 freeze `d6bd75d`) | **194** |
| After H-4 | **213** |

Per-step progression: 194 → **197** (H-4.1) → **199** (H-4.2) → **203** (H-4.3) → **206** (H-4.4) →
**209** (H-4.5) → **212** (H-4.6) → **213** (H-4.7). **Zero regressions at every step.**

## 3. New tests added (+19, all in `test_nexus_lifecycle.py`)

| Step | Tests |
|---|---|
| 1 fail-fast init | `test_init_fails_without_client_or_key`, `test_init_proceeds_with_injected_client`, `test_init_proceeds_with_env_key` |
| 2 budget | `test_step_budget_configurable`, `test_step_budget_default_is_five` |
| 3 terminate | `test_terminate_sets_cancel_signal`, `test_terminate_kills_inflight_process`, `test_cancel_before_run_yields_cancelled`, `test_cancel_mid_run_persists_cancelled_step` |
| 4 cancellation wiring | `test_operator_cancel_via_db_signal`, `test_resolve_exit_status_maps_agent_status`, `test_resolve_exit_status_falls_back_to_exit_code` |
| 5 TIMED_OUT | `test_budget_exhaustion_times_out`, `test_wallclock_timeout_times_out`, `test_timed_out_distinct_from_failed` |
| 6 resume | `test_resume_continues_from_checkpoint`, `test_resume_fails_closed_without_prior_steps`, `test_resume_revalidates_governance` |
| 7 audited run | `test_audited_real_run` |

Final gates: **213 passed · ruff clean · mypy clean (60 files)**.

## 4. Architecture impact summary

- **RuntimeRegistry:** unchanged (`@runtime_registry.register("nexus")`; routing intact).
- **`AgentRuntimeAdapter` contract:** unchanged — `resume_goal` is adapter-local (not added to the ABC),
  so CLI adapters (Gemini/Claude) are untouched.
- **Orchestrator:** one minimal change — finalize via `resolve_exit_status(result)`; CLI exit_code
  mapping preserved as a fallback. No pipeline/architecture change.
- **SandboxManager abstraction:** preserved — cancellation reuses the existing `SandboxProcess.terminate()`;
  `execute_command` still routes through `SandboxManager`; S-4 workspace confinement untouched.
- **Governance:** preserved and **re-enforced on resume** (no bypass).
- **Memory schema / events / audit:** unchanged — terminal states reuse existing `ExecutionStatus`
  values and existing `agent_steps`/`workflow_checkpoints`/artifact persistence; cancel signal reuses
  the existing `exit_status` column. **No schema changes, no migrations.**
- **Scheduler architecture:** untouched.

## 5. Remaining gaps to Production Ready

Pilot is reached (below); **Production Ready** is explicitly **not** a v1.1.0 goal and still requires:
- **Real search provider in production** — H-4 ships the `SearchProvider` seam (H-2) and a safe
  no-provider default; a concrete vetted provider + egress hardening remain.
- **Automatic orphan-detection → resume** (P2) — resume is currently *invocable*, not auto-triggered;
  needs an orphan-execution monitor (scheduler concern).
- **In-container file I/O ceiling (R-05)** (P2) — host-side workspace floor (S-4) prevents escape; the
  in-container ceiling is defense-in-depth.
- **Advanced replanning / dependency-graph planning**, multi-backend support, per-step streaming (P2).
- **Real CLI runtime integration** (Gemini/Claude still stubbed) — separate track.
- **Broader hardening:** structured-call retry/repair policy, dedicated `AGENT_*` event taxonomy (vs.
  reused audit path), scaled real-world soak testing.

## 6. Pilot reclassification recommendation

Success criteria (all demonstrated): fail-fast init ✅ · configurable budgets ✅ · `terminate()` ✅ ·
cancellation ✅ · `TIMED_OUT` lifecycle ✅ · `resume_goal()` ✅ · audited real run ✅ · all tests
passing (213) ✅ · ruff clean ✅ · mypy clean ✅ · zero regressions ✅.

> **Recommendation: APPROVE reclassification Nexus Experimental → Pilot.**

Conditioned: **Pilot, not Production Ready** (§5 gaps); effective on commit (H-4 currently uncommitted);
production search requires a real injected `SearchProvider` bound to the sandbox network policy; the
`architecture-status-summary.md` Nexus-row upgrade (Experimental → Pilot) is a **separately authorized**
documentation step (not performed here).

**Stopped after implementation + validation evidence. No commit, no tag, no maturity-doc changes —
awaiting review.**
