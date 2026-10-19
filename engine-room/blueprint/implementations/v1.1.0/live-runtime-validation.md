# Live Runtime Validation

> v1.1.0 bring-up · real LLM (multi-provider), real governance, real persistence.

## Setup
Governed execution: `TaskRecord` + approved `ApprovalRecord` + `ExecutionRecord(runner="nexus",
repository=".")`; `workspace_root` registered in the repository registry (governance passes).

## Nexus agent — observed
- `get_runtime_adapter("nexus", …)` → `NexusRuntimeAdapter` (registry id `nexus`; legacy `hermes`
  alias resolves to the same class).
- `initialize()` (fail-fast LLM gate) → OK · `validate_goal()` (governance) → `RepositoryValidated` +
  `RuntimeAuthorized` audited.
- `execute_goal()` real LLM-driven loop → terminal state with artifacts persisted:
  `{agent_plan, agent_trajectory, diff, summary}`.

| Run | Status | Notes |
|---|---|---|
| initial | `completed` / exit 0 | full plan→finish, artifacts persisted |
| recovery-resume | `completed` / exit 0 | continued from checkpoint to completion |
| one repeat (Groq) | `failed` / exit 1 | model emitted a malformed tool-call → **honest FAILED** (by design, not a crash) |

**Completion criterion "≥1 runtime executes successfully": MET** (multiple `completed` runs). Honest
failure path also confirmed (malformed model output → FAILED, never silent success).

## Approval / audit / artifacts / checkpoint / completion
- approval: approved record honored; A-001 owners active.
- audit: `RuntimeAuthorized`, `RepositoryValidated` (×4 across runs).
- artifacts: plan + trajectory + diff + summary persisted per run.
- checkpoint: per-step `WorkflowCheckpointRecord` written (39 total across runs).
- completion: truthful terminal `status`/`exit_code` (completed/failed/timed_out distinct).

## CLI runtimes (gemini/claude)
Registry resolves both, but they are **subprocess stubs** — no real model integration. Live
model execution is the `nexus` agent only. Classification: **Experimental**.

## Verdict
Nexus agent runtime: **Pilot Ready** (governed, recoverable, honest). gemini/claude: **Experimental**.
