# Nexus Execution Trace Analysis (AP-105)

> End-to-end trace of how a Nexus run actually executes in the repository, from production trigger to
> persistence — distinguishing the **real LLM path** from the **mock path**, with line evidence.
> Audit-only.

---

## 1. Is Nexus reachable in production? — Yes (conditionally)

Nexus is **wired into the live pipeline**, not test-only:

1. `WorkflowOrchestrator` is constructed and `register_listeners()` is called at startup
   (`api.py:141-144`).
2. It subscribes to `APPROVAL_GRANTED` → `on_approval_granted` → `run_execution_flow`
   (`orchestrator.py:49,79-101`).
3. The runner is chosen from the task: `runner = task.runtime_id or "gemini"`
   (`orchestrator.py:143`). A task with `runtime_id="nexus"` (real column, `models.py:48`) routes here.
4. The adapter is resolved via the registry with the **real** `openrouter_client` and settings
   (`orchestrator.py:166-175`).
5. The agent branch runs: `validate_goal` → `execute_goal` → `checkpoint` → `persist`
   (`orchestrator.py:210-224`).

**Conclusion:** Nexus is a production-routable runtime. What it *does* once routed is the subject below.

## 2. The goal is dynamic; the plan is not

- **Goal** comes from the task description (`goal:` prefix stripped, `orchestrator.py:149-150`) and is
  passed to `execute_goal(goal)` — genuinely dynamic per task.
- **Plan** is a hardcoded 3-step literal (`nexus.py:147-151`), identical regardless of goal, and is
  **never read to drive the loop** — it is only persisted as the `agent_plan` artifact
  (`nexus.py:344-353`). The plan is decorative.

## 3. The fork: mock path vs real path

`execute_goal` computes `is_mocked` (`nexus.py:186-191`):

```
is_mocked = (not openrouter_client)
            or isinstance(openrouter_client.complete, AsyncMock)
            or "test-key" in settings.openrouter.api_key
```

- **Production config** (real `OpenRouterClient`, real API key): `is_mocked = False` → the **real LLM
  branch** executes (`nexus.py:212-234`): `await openrouter_client.complete(prompt)`, JSON parse of
  `{thought, tool_name, tool_arguments}`, with a keyword-heuristic fallback to `finish` on parse error.
- **Default / test / dev config** (no client, `AsyncMock`, or `"test-key"`): the **hardcoded decision
  branch** runs (`nexus.py:193-211`): step 0 `web_search`, step 1 `write_file mcp_report.md`, step 2+
  `finish`.

**Both branches share two non-negotiable facts:**
- `web_search` is **always simulated** (`nexus.py:76-86`) — even when a real LLM selects it, the result
  is canned. Real reasoning over fake observations.
- The return is **always `exit_code: 0`** (`nexus.py:284-289`), so the orchestrator always finalizes
  `SUCCESS` (`orchestrator.py:227`).

## 4. Per-step persistence (real)

Each loop iteration (`nexus.py:157-279`):
1. `heartbeat()` → updates `ExecutionRecord.last_heartbeat` (real DB write, `nexus.py:291-299`).
2. Decides action (mock or LLM, §3).
3. Executes the tool (`_execute_tool`, real for file/command; canned for search).
4. Writes a real `AgentStepRecord` (`agent_steps`) with thought/tool/args/result (`nexus.py:250-261`).
5. Appends to in-memory trajectory (`nexus.py:263-271`).
6. Writes a real `WorkflowCheckpointRecord` (`workflow_checkpoints`) `{step, plan}` (`nexus.py:274-277`).

The persistence *mechanism* is genuine and tested (`test_nexus.py:110-122`). In the **mock** path the
*content* persisted is synthetic; in the **real** path it is genuine model output over (still) canned
search observations.

## 5. Finalization (`persist`, real)

`persist()` (`nexus.py:338-405`) writes four real artifacts when present: `agent_plan` (decorative),
`agent_trajectory`, `summary` (real `summarize()` LLM call, `nexus.py:316-336`), and a `diff` via real
`git diff` subprocess if the repo is a git worktree. Verified by `test_nexus.py:159-172`.

## 6. Lifecycle gaps observed in the trace

- **No `terminate()` in the agent path.** The orchestrator never calls it for `AgentRuntimeAdapter`, and
  Nexus's `terminate()` is `pass` (`nexus.py:312-314`). A long/looping run cannot be cancelled.
  (Contrast: CLI runners call `terminate()` on timeout, `claude.py:124`.)
- **No resume.** `execute_goal` always reinitializes (`nexus.py:138-139`); nothing reads the
  checkpoints back. There is no `resume_goal` (unlike research/briefing). Checkpoints are write-only.
- **Heartbeat has no consumer.** `last_heartbeat` is written but no orphan-reaper acts on it (audit 09).

## 7. Test reality

`tests/unit/execution/test_nexus.py` (4 tests) exercises: init (no-crash), validate-fail/success
(real governance), execute+checkpoint (asserts step/checkpoint counts), summarize+persist (asserts
artifact types + summary content). **All run through the mock path** (no real LLM). They prove the
*plumbing* (persistence, governance, artifact shape) — they do **not** exercise real LLM reasoning,
real search, termination, or resume.

## 8. Trace verdict

The trace shows a **real, DB-integrated ReAct skeleton** that is production-routable and persists
genuine state, wrapped around **simulated search, a decorative hardcoded plan, an always-success exit
code, an in-module test mock, and missing terminate/resume**. The machinery is real; the *autonomy and
honesty of outcomes* are not yet.
