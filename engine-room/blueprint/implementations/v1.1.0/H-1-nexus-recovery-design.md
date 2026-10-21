# H-1 — Nexus Recovery Design (v1.1.0)

> **Track H · Design only.** How an interrupted Nexus run resumes, and how checkpoints evolve from
> write-only to recoverable — reusing the existing memory/checkpoint architecture and the
> research/briefing resume precedent (Rules 4, 7). No code. Answers Q5 (resume) and Q7 (checkpoints).

---

## 1. Problem (evidence)

Checkpoints are **write-only**: `execute_goal` always restarts fresh (`nexus.py:138-139`); checkpoints
are written each step (`nexus.py:274-277`) but never read; there is **no `resume_goal`** (only
`research.py:361 resume_research_run` and `briefing.py:250 resume_briefing_run` exist). An interrupted
run loses all progress (AP-105 Cap 12 = Not Present, Gap 4).

## 2. Resume principle — reconstruct, don't re-run

The data needed to resume **already exists** and is persisted every step:

- **Trajectory** ← all `AgentStepRecord` rows for the `execution_id` (`step_index`, `thought`,
  `tool_name`, `tool_arguments`, `tool_result`) — `nexus.py:250-261`, schema `models.py:344`.
- **Plan + cursor** ← the latest `WorkflowCheckpointRecord` for the `workflow_id` (state
  `{step, plan}`) — `nexus.py:301-310`.

Therefore resume requires **no schema change**: it is a *read* capability over already-written data.

## 3. `resume_goal` (conceptual contract)

A new adapter method, mirroring the existing resume precedent:

```
resume_goal(execution_id) :
  1. Load all agent_steps for execution_id, ordered by step_index → rebuild self.trajectory
  2. Load latest checkpoint for workflow_id == execution_id → restore self.plan and the cursor
  3. Set step_index = (max persisted step_index) + 1
  4. Re-enter the loop at DECIDING (lifecycle-design), continuing until a terminal state
```

- **Entry point:** only from the `CHECKPOINTED` boundary (lifecycle-design §2) — a half-written step is
  never resumed mid-tool.
- **Idempotency:** resume must not duplicate the last completed step; the `step_index` cursor +
  `replace_existing` semantics guarantee monotonic progress. Re-emitting a step already persisted is
  prohibited.
- **Precedent alignment:** signature/semantics mirror `resume_research_run`/`resume_briefing_run` so the
  codebase has one resume idiom (Rule 7, no divergent patterns).

## 4. Checkpoint evolution (write-only → recoverable)

The **recovery contract** a checkpoint must satisfy to be resumable:

| Requirement | Met by today's data? | Design note |
|---|---|---|
| Identify the run | ✅ `workflow_id == execution_id` | unchanged |
| Restore plan | ✅ `state.plan` | becomes the *real* (generated) plan |
| Restore cursor | ✅ `state.step` (+ `agent_steps` max index) | use max persisted `step_index` |
| Restore trajectory | ✅ via `agent_steps` query | not the checkpoint's job |
| Mark resumability | ⚠️ implicit | design: treat "latest checkpoint exists & run non-terminal" as resumable; an explicit resumable marker is an *optional additive* enum value, decided at impl AP |

**Decision:** keep checkpoints as **per-step progress markers** (current behavior) and treat
`agent_steps` as the **trajectory system of record**. This avoids duplicating the trajectory into
checkpoint `state` (no write amplification, no schema growth).

## 5. Who triggers resume?

- **In scope (design):** the *capability* to resume (the `resume_goal` contract) and its correctness.
- **Out of scope (deferred):** an **automatic** orphan-detection→resume trigger. That depends on an
  orphan-execution monitor (a scheduler/recovery concern, explicitly deferred and noted in AP-105 Cap 13
  / `09-operational-capabilities.md`). v1.1.0 provides resume as an **invocable** capability (operator-
  or orchestrator-initiated), not an autonomous self-heal.

## 6. Failure handling during resume

- If `agent_steps`/checkpoint are absent or inconsistent → resume **fails closed** (raises; run remains
  in its prior terminal/failed state) rather than silently starting fresh and masking data loss.
- Resume re-validates the goal through governance before continuing (no bypass of Rule 5/governance).

## 7. Architecture preservation

- Pure reuse of `AgentStepRecord` + `WorkflowCheckpointRecord` + memory service (Rules 4, 7).
- No new tables/migrations at design level; any enum addition is additive and impl-AP-gated.
- Mirrors existing resume idiom → no hidden coupling, no new pattern (Rules 9, 8).

## 8. Tier mapping

Resume (working + tested) is a **Pilot** requirement (Q9). Experimental does **not** require resume —
honesty (Pillar A) is the Experimental bar; recoverability is the Pilot bar.
