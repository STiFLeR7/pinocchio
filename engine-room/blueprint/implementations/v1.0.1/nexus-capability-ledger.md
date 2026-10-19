# Nexus Capability Ledger (AP-105)

> The authoritative, evidence-based ledger of **every** Nexus capability, classified by current
> repository reality only — not intention, roadmap, or design. Audit-only; no code was changed.
>
> **Subject:** `nexus/execution/runners/nexus.py` (`NexusRuntimeAdapter`) @ v1.0.1 working tree.
> **Classification states:** Implemented · Partially Implemented · Simulated · Stubbed · Mocked ·
> Designed Only · Not Present.

---

## Ledger

| # | Capability | Current State | Evidence | Risk | Required Work | Priority |
|---|---|---|---|---|---|---|
| 1 | Goal validation (governance) | **Implemented** | `nexus.py:57-72` → `GovernanceManager.validate_execution(runtime="nexus")`; `test_nexus.py:33-78` | Low | None | — |
| 2 | Dynamic planning | **Simulated** | `nexus.py:147-151` — a hardcoded 3-step plan, identical for any goal; not consulted to drive the loop (persisted as decorative artifact only) | High — Nexus is advertised as a "planning agent" but the plan is static and decorative | Generate the plan from the goal via LLM and let it drive the loop | P1 |
| 3 | Action selection (ReAct loop) | **Partially Implemented** | `nexus.py:212-234` — real `openrouter_client.complete(prompt)` in production config; brittle JSON parse + keyword heuristic fallback | Medium — no schema-validated tool calls; silent fallback to `finish` | Structured/validated tool-call output | P1 |
| 4 | Mock decision branch (in prod module) | **Mocked** | `nexus.py:7` imports `AsyncMock`; `nexus.py:186-211` `is_mocked` branch emits hardcoded `web_search→write_file→finish` steps | High — test scaffolding lives in the production code path | Remove `AsyncMock` import from prod; relocate simulation to tests/fixtures | P0 |
| 5 | Tool: `read_file` | **Implemented** | `nexus.py:88-94` — real `open()/read()` | Medium — no path confinement | Sandbox/whitelist paths | P2 |
| 6 | Tool: `write_file` | **Implemented** | `nexus.py:96-105` — real `makedirs`+`write` to host FS | Medium — writes host filesystem outside sandbox | Confine writes to sandbox/workdir | P1 |
| 7 | Tool: `execute_command` | **Implemented** | `nexus.py:107-131` — real `SandboxManager.execute(...)`, ADR-010 timeout | Medium — relies on default-off sandbox (A-006) | Resolve with A-006 | P1 |
| 8 | Tool: `web_search` | **Simulated** | `nexus.py:76-86` — returns canned "MCP" text if `"mcp" in query`, else `"No results found"`; **no provider call** (runs in both mock and real branches) | High — the headline research capability returns fabricated results | Integrate a real search/retrieval provider | P0 |
| 9 | Agent step persistence | **Implemented** | `nexus.py:250-261` real `AgentStepRecord`; schema `models.py:344` (`agent_steps`); `test_nexus.py:110-114` | Low | None | — |
| 10 | Trajectory capture | **Implemented** | `nexus.py:263-271` in-memory + persisted per step | Low (content can be mock-generated in mock config) | None (content quality follows #2/#4) | — |
| 11 | Checkpoint persistence | **Implemented** | `nexus.py:301-310` real `WorkflowCheckpointRecord`; schema `models.py` (`workflow_checkpoints`); `test_nexus.py:116-122` | Low (write) | None for write | — |
| 12 | Recovery / resume | **Not Present** | No `resume_goal`; `execute_goal:138-139` always starts fresh (`step_index=0`, `trajectory=[]`); only `research.py:361`/`briefing.py:250` expose `resume_*` | High — checkpoints imply resumability that does not exist | Implement resume-from-checkpoint for the agent loop | P1 |
| 13 | Heartbeat | **Implemented** | `nexus.py:291-299` real `last_heartbeat` write each step | Low — no orphan-reaper consumes it (audit 09) | Orphan-execution monitor | P2 |
| 14 | Termination / cancellation | **Not Present (no-op)** | `nexus.py:312-314` body is `pass`; **never invoked** by orchestrator agent branch (CLI runners *do* call `terminate()`, `claude.py:124/188`) | High — a runaway agent loop cannot be cancelled | Cooperative cancellation honored by the loop | P1 |
| 15 | Summarization | **Implemented** | `nexus.py:316-336` real `openrouter_client.complete` | Low | None | — |
| 16 | Artifact persistence (plan/trajectory/summary/diff) | **Implemented** | `nexus.py:338-405`; `test_nexus.py:159-172` | Low | None | — |
| 17 | Initialize / API-key check | **Stubbed** | `nexus.py:47-55` reads key then `pass` when absent | Medium — proceeds without a usable LLM key | Fail-fast on missing key | P2 |
| 18 | Exit-status fidelity | **Simulated** | `nexus.py:284-289` returns `"exit_code": 0` unconditionally; orchestrator maps to `SUCCESS` (`orchestrator.py:216,227`) | High — failures are reported as success | Derive real exit code from loop outcome | P0 |
| 19 | Step bound | **Implemented** | `nexus.py:153` `max_steps=5` (hardcoded) | Low | Make configurable | P3 |
| 20 | Runtime registry integration | **Implemented** | `nexus.py:24` `@runtime_registry.register("nexus")`; `__init__.py:54`; routing `orchestrator.py:143,168,210-216` | Low | None | — |

---

## Roll-up by state

- **Implemented (10):** goal validation, read_file, write_file, execute_command, agent-step persistence,
  trajectory capture, checkpoint persistence, heartbeat, summarization, artifact persistence, registry,
  step bound. *(Real, evidenced, mostly tested.)*
- **Partially Implemented (1):** action selection (real LLM loop, fragile parsing).
- **Simulated (3):** dynamic planning, `web_search`, exit-status fidelity.
- **Mocked (1):** in-module `AsyncMock` decision branch.
- **Stubbed (1):** initialize / API-key check.
- **Not Present (2):** recovery/resume, termination/cancellation.
- **Designed Only / Not Present (others):** none beyond the above.

## Priority hot-list

- **P0 (block honest production):** remove `AsyncMock` from prod path (#4), real search (#8), real exit
  code (#18).
- **P1 (core agent integrity):** dynamic planning (#2), robust action parsing (#3), sandbox-confined
  writes (#6), execute_command/sandbox (#7), resume (#12), termination (#14).
- **P2/P3:** path confinement (#5), orphan monitor (#13), fail-fast init (#17), configurable bound (#19).

*All "Required Work" entries are descriptive of the gap only — AP-105 proposes no implementation.*
