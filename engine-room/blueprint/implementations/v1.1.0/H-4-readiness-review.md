# H-4 — Pilot Readiness Review (Nexus Lifecycle Safety)

> **Inventory only — no implementation, no source changes.** The remaining work to move Nexus
> **Experimental → Pilot**, classified per item with root cause, implementation files, test
> requirements, architecture impact, and risk. Sources: `H-2-gap-prioritization.md`,
> `H-2-implementation-plan.md`, `ADR-nexus-v1.1-foundation`, `H-1-nexus-lifecycle-design.md`,
> `H-1-nexus-recovery-design.md`, and current source at the post-H-2 working tree (`b734c13` + H-2).

---

## 1. Where Nexus stands after H-2

**Experimental achieved:** no prod mock · provider-backed search · goal-derived planning · structured
tool-calls · truthful exit status (`ADR-hermes-experimental`). **Pilot gate (`ADR-nexus-v1.1-foundation`
Q9) still requires:** wired+tested cancellation · working+tested resume · fail-fast init · configurable
budget · timeout lifecycle · one audited real governed run. R-05 file-confinement **floor is already done
(S-4)**; the in-container ceiling is P2.

## 2. Pilot (P1) item inventory

### P1-1 — `terminate()` becomes functional
- **Root cause:** `terminate()` is `pass` (`nexus.py:324-326`); no cancellation mechanism exists.
- **Implementation files:** `nexus/execution/runners/nexus.py` (set + honor a cancel signal; kill an
  in-flight `execute_command` via `SandboxProcess.terminate()`, `provider.py:47-50`).
- **Test requirements:** `terminate()` sets the signal; an in-flight sandbox process is killed; idempotent
  when already terminal.
- **Architecture impact:** Low–Medium — adapter-internal + reuse of the existing sandbox terminate; no
  new mechanism. Pairs with P1-2 (cancellation) for the wiring.
- **Risk:** Medium — must not deadlock the async loop; cooperative (no forced task kill).

### P1-2 — Cooperative cancellation (signal + observation + wiring)
- **Root cause:** the loop never checks for cancellation; the orchestrator agent branch never calls
  `terminate()` (`orchestrator.py:210-216`).
- **Implementation files:** `nexus.py` (check a **DB-observable** cancel signal at state boundaries —
  before DECIDING and before TOOL_EXECUTING, per `H-1-nexus-lifecycle-design.md` §4); `orchestrator.py`
  (invoke `terminate()` on operator action / timeout — the missing wiring, one invocation point).
- **Test requirements:** cancel between steps → `CANCELLED` terminal + `cancelled` exit; latency bounded
  to one tool execution; cancel during `execute_command` kills the subprocess.
- **Architecture impact:** **Medium — touches the orchestrator** (kept minimal). Signal should be
  DB-observable (consistent with the DB-backed approval model, Rule 5) to avoid hidden coupling.
- **Risk:** Medium–High — the only item that edits the orchestrator; needs careful minimal wiring +
  a possible **additive** `CANCELLED` exit/status value (additive enum, no schema redesign).

### P1-3 — `resume_goal()` (resumable recovery)
- **Root cause:** checkpoints are write-only; `execute_goal` always restarts (`nexus.py` plan
  re-derive); no `resume_goal` (only `research.py`/`briefing.py` resume).
- **Implementation files:** `nexus.py` (`resume_goal(execution_id)`: load `AgentStepRecord`s ordered by
  `step_index` → rebuild trajectory; load latest `WorkflowCheckpointRecord` for `workflow_id` → restore
  plan + cursor; `step_index = max+1`; re-enter loop; re-validate goal via governance); `base.py`
  (`AgentRuntimeAdapter` — **additive optional** method, default to preserve CLI adapters).
- **Test requirements:** resume rebuilds trajectory; continues from cursor; no duplicate step;
  absent/inconsistent data → **fail closed**; governance re-validated on resume.
- **Architecture impact:** Low — **read over existing schema** (`H-1-nexus-recovery-design.md`); no
  migration; mirrors the existing resume idiom (Rule 7). Auto-trigger is **P2** (orphan monitor).
- **Risk:** Low–Medium — idempotency/cursor correctness is the main hazard; bounded by fail-closed.

### P1-4 — Fail-fast initialization
- **Root cause:** `initialize()` checks for a key then `pass` if absent (`nexus.py:48-56`).
- **Implementation files:** `nexus.py` (`initialize` raises on missing usable key — `ConfigurationError`
  or `ExecutionEngineError`).
- **Test requirements:** missing key → raises (run does not proceed); present key → proceeds.
- **Architecture impact:** Low — adapter-internal; aligns with the A-001 fail-fast discipline.
- **Risk:** Low — must not break tests that construct the adapter without a key purely to test other
  methods (use injected client/provider, as H-2 tests already do).

### P1-5 — Configurable execution budget
- **Root cause:** `max_steps = 5` hardcoded (`nexus.py:205`).
- **Implementation files:** `nexus.py` (read budget from settings); `nexus/config.py` (**additive**
  field, e.g. `execution.agent_max_steps`).
- **Test requirements:** configured value honored; default preserved when unset.
- **Architecture impact:** Low — additive config; no schema/migration.
- **Risk:** Low.

### P1-6 — Timeout lifecycle handling (`TIMED_OUT`)
- **Root cause:** budget/wall-clock exhaustion currently yields `exit_code 1/failed` (H-2 honest binary)
  but not a distinct `TIMED_OUT` terminal; no wall-clock timeout enforcement in the loop.
- **Implementation files:** `nexus.py` (enforce the ADR-010 wall-clock timeout via
  `resolve_execution_timeout`, already imported; budget/time exhaustion → `TIMED_OUT` distinct from
  COMPLETED/FAILED); possibly `core/types.py` (**additive** `TIMED_OUT` already exists in
  `ExecutionStatus`; an `ExitStatus.TIMED_OUT` may be additive); `orchestrator.py` only if a distinct
  finalization is wanted (else maps to FAILURE).
- **Test requirements:** budget exhaustion → `TIMED_OUT`; wall-clock exceed → `TIMED_OUT`; distinct from
  genuine completion.
- **Architecture impact:** Low–Medium — reuses `resolve_execution_timeout`; any new `ExitStatus` value is
  **additive** (no schema redesign). `ExecutionStatus.TIMED_OUT` already exists (`types.py:41`).
- **Risk:** Low–Medium — interaction with the orchestrator finalization mapping (keep additive).

### Pilot-gate completion item — one audited real governed run
- **Root cause:** evidence requirement, not a code gap.
- **Implementation files:** none (a test/fixture or a documented run with a real provider).
- **Test requirements:** an end-to-end governed run producing genuine output, audited.
- **Architecture impact:** none.
- **Risk:** Low (depends on a real `SearchProvider`/LLM being available in the run environment).

## 3. Dependency & sequencing

```
P1-4 fail-fast init   (independent, low risk)
P1-5 configurable budget (independent, low risk)
P1-1 terminate ──► P1-2 cancellation (+orchestrator wiring)   [state machine]
P1-6 TIMED_OUT  ──► (uses budget P1-5 + lifecycle)
P1-3 resume_goal (independent of cancellation; read-reconstruction)
audited real run ──► after the above, with a real provider
```

Lowest-risk first (P1-4, P1-5), then the lifecycle state machine (P1-1/P1-2/P1-6), then resume (P1-3),
then the audited run.

## 4. Risk summary

| Item | Risk | Why |
|---|---|---|
| P1-1 terminate | Medium | async cancellation correctness |
| P1-2 cancellation + wiring | **Medium–High** | only orchestrator edit; possible additive enum |
| P1-3 resume_goal | Low–Medium | idempotency/cursor; read-only over schema |
| P1-4 fail-fast init | Low | adapter-internal |
| P1-5 configurable budget | Low | additive config |
| P1-6 TIMED_OUT | Low–Medium | orchestrator finalization mapping |
| audited real run | Low | environment/provider dependency |

## 5. Architecture impact summary (all items)

- **No schema redesign / no migrations.** `ExecutionStatus.TIMED_OUT`/`CANCELLED` already exist
  (`types.py`); any `ExitStatus` addition is additive. Resume is a read over existing tables.
- **One orchestrator touch** (P1-2 wiring) — the only edit outside the adapter; kept to a single
  invocation point.
- **Runtime V2 contract** extended only additively (`resume_goal` optional on the agent adapter).
- **Governance / registry / scheduler / events / Track-S sandbox seam** preserved.

## 6. Pilot readiness verdict

Nexus is **Experimental-complete** and **Pilot-incomplete**. The six P1 items + one audited run are
well-scoped, low-to-medium risk, and require **no schema changes or migrations** — the heaviest item is
the orchestrator cancellation wiring. Detailed scope/boundaries in `H-4-scope-definition.md`.

**No implementation performed.** Inventory only.
