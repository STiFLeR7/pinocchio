# Recovery Validation (Failure Injection)

> v1.1.0 bring-up · checkpoint recovery across a simulated restart.

## Method
1. **Interrupt:** run the nexus agent with the wall-clock budget forced to 0 → the run **times out**
   at the first loop boundary, persisting a `TIMED_OUT` marker step + checkpoint.
2. **Restart:** construct a **fresh `NexusRuntimeAdapter` instance** for the same `execution_id`
   (simulating a process restart — no in-memory state carried over).
3. **Resume:** `resume_goal()` reconstructs trajectory from `agent_steps` + latest checkpoint,
   re-validates governance, and continues to a terminal state.

## Observed
| Phase | status | steps | checkpoints |
|---|---|---|---|
| interrupt | `timed_out` | 1 | 1 |
| resume (fresh adapter) | `completed` | 3 | 3 |

- **continuity_no_corruption:** `true` (steps and checkpoints monotonically grew; prior records intact).
- **audit continuity:** audit log preserved and appended across the restart (no gaps/rewrites).
- **governance on resume:** re-validated (no bypass) — fail-closed if state were missing.

This exercises the Phase-6 intent (interrupt during runtime → recover) with real persistence: the
restart did not corrupt state, lose the trajectory, or break the audit chain.

## Verdict
Recovery / checkpointing: **Pilot Ready** — resume-from-checkpoint verified end-to-end with continuity.
