# H-4 — Scope Definition (Nexus Experimental → Pilot)

> **Definition only — no implementation, no source changes.** Fixes the scope, boundaries, gate, and
> deliverables for a future, separately-authorized H-4 implementation AP. Derived from
> `H-4-readiness-review.md`, `ADR-nexus-v1.1-foundation` (Pilot gate), and the H-1 lifecycle/recovery
> designs.

---

## 1. Mission

Move Nexus from **Experimental** (honest) to **Pilot** (honest **and** lifecycle-safe **and**
contained) by delivering cooperative cancellation, resumable recovery, fail-fast init, a configurable
budget, and timeout lifecycle handling — without touching governance, scheduler, memory schema, the
event taxonomy, or the runtime-abstraction contract beyond the minimum each item requires.

## 2. In scope (H-4)

| ID | Item | Tier |
|---|---|---|
| P1-1 | Functional `terminate()` (cooperative cancel + in-flight sandbox kill) | Pilot |
| P1-2 | Cooperative cancellation: DB-observable signal, loop-boundary checks, **orchestrator wiring** | Pilot |
| P1-3 | `resume_goal(execution_id)` — read-reconstruct trajectory + plan, continue, fail-closed | Pilot |
| P1-4 | Fail-fast initialization (raise on missing usable key) | Pilot |
| P1-5 | Configurable execution budget (additive config; default preserved) | Pilot |
| P1-6 | Timeout lifecycle: enforce ADR-010 wall-clock + budget → `TIMED_OUT` terminal | Pilot |
| P1-7 | One audited real governed run producing genuine output | Pilot (evidence) |

## 3. Explicitly OUT of scope (reject if proposed)

- **Automatic** orphan-detection → resume trigger (needs an orphan monitor; **P2**, scheduler concern).
- In-container file I/O ceiling for R-05 (**P2**, Track S / H-5; floor already done by S-4).
- Advanced/dependency-graph replanning; new tools; non-OpenRouter backends; per-step Discord streaming
  (master-design Q10 deferred list).
- A new `AGENT_*`/`EXECUTION_*` event taxonomy (impl-AP decision; reuse existing audit path).
- **Production Ready** status (explicitly not a v1.1.0 goal).
- Any schema redesign or migration; any change to governance/approval/registry/scheduler architecture.

## 4. Hard boundaries (must hold)

1. **No schema redesign, no migrations.** `ExecutionStatus.TIMED_OUT`/`CANCELLED` already exist; any
   `ExitStatus` addition is **additive**. Resume is a read over existing `agent_steps`/
   `workflow_checkpoints`.
2. **One orchestrator touch only** — the P1-2 cancellation/timeout invocation; a single, minimal wiring
   point (`orchestrator.py:210-216`), no architecture change.
3. **Runtime V2 contract** extended only additively (`resume_goal` optional; CLI adapters untouched).
4. **Preserve** the H-2 honesty guarantees, the Track-S sandbox containment seam (S-4 / S-2/S-3), the
   governance gate, RuntimeRegistry, and `AgentStepRecord` schema.
5. **Cooperative cancellation only** — no forced async-task/thread kill.

## 5. Lifecycle target (from `H-1-nexus-lifecycle-design.md`)

Terminal states: `COMPLETED` · `FAILED` · `TIMED_OUT` · `CANCELLED`, each mapped to a faithful exit
status. Resume entry only from the `CHECKPOINTED` boundary. Cancellation observed at state boundaries
(before DECIDING / before TOOL_EXECUTING), bounding latency to one tool execution.

## 6. Test strategy (H-4, RED-first)

| Item | Required tests |
|---|---|
| P1-1/P1-2 | cancel between steps → `CANCELLED`+`cancelled` exit; in-flight `execute_command` killed; latency ≤ one tool exec; orchestrator invokes terminate on timeout/operator |
| P1-3 | resume rebuilds trajectory; continues from cursor; no duplicate step; missing/inconsistent data → fail-closed; governance re-validated |
| P1-4 | missing key → raises; present key → proceeds |
| P1-5 | configured budget honored; default preserved |
| P1-6 | budget/wall-clock exhaustion → `TIMED_OUT` (distinct from COMPLETED/FAILED) |
| P1-7 | one audited end-to-end governed run with a real provider produces genuine output |

All under TDD (RED→GREEN→regression); full suite + ruff + mypy green; zero regressions; CLI runtimes,
sandbox suites, governance, scheduler, e2e unaffected.

## 7. Pilot promotion gate (evidence-defined)

Experimental **plus**: wired+tested cancellation (P1-1/P1-2) · working+tested resume (P1-3) · fail-fast
init (P1-4) · configurable budget (P1-5) · timeout lifecycle (P1-6) · R-05 file confinement (**done,
S-4**) · **one audited real governed run** (P1-7). AP-105 Caps 12 & 14 = Implemented; Caps 17 & 19 ≥
Implemented.

## 8. Suggested sequencing (gated, not authorized here)

```
H-4.1  fail-fast init (P1-4) + configurable budget (P1-5)   [low risk, independent]
H-4.2  lifecycle state machine + terminate + cancellation + orchestrator wiring (P1-1/P1-2)
H-4.3  TIMED_OUT enforcement (P1-6)
H-4.4  resume_goal (P1-3)
H-4.5  audited real governed run (P1-7) + Pilot closure
```

Each step is separately reviewed; H-4 begins only on explicit approval.

## 9. Deliverables expected from a future H-4 implementation AP

Implementation report; lifecycle/cancellation validation; resume validation; timeout/budget validation;
audited-run evidence; Pilot readiness assessment; `ADR-hermes-pilot` — mirroring the H-2 deliverable set.

## 10. Status

Scope definition only. No code, no migration, no commit. H-4 is **gated** pending explicit approval;
this document does **not** authorize implementation.
