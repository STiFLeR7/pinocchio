# H-2 — Nexus Honesty Design (Track H, v1.1.0 "Containment")

> **Design only. No implementation, no source changes, no migrations, no runtime behavior change, no
> opportunistic refactoring.** This document specifies *how* H-2 makes the Nexus production path honest
> (Prototype → **Experimental**), and designs through the Pilot capabilities (terminate/resume) so the
> sequencing is coherent. Implementation is a separately-gated AP. Grounded in source at commit
> `b734c13` and the accepted H-1 designs + `ADR-nexus-v1.1-foundation`.

---

## 1. Objective & boundary

**Objective:** eliminate simulation from the Nexus production path and make outcomes truthful, so the
runtime earns **Experimental** under the `ADR-nexus-v1.1-foundation` gate — while preserving the sound
skeleton (governance, persistence, registry, real file/command tools) AP-105 §4 told us not to lose.

**Boundary (Architecture Rules 1–10):** no change to governance, approval, scheduler, memory schema,
event taxonomy, or the runtime-abstraction contract beyond the minimum a listed gap requires. No new
tools (the five stay: `web_search`, `read_file`, `write_file`, `execute_command`, `finish`). No new
agent types, model backends, or migrations.

**H-2 implementation target = the six P0 items** (`H-2-gap-prioritization.md` §2). P1 (terminate,
resume, fail-fast init, budget) and P2 are designed here but built in H-3…H-5.

## 2. The honest execution model (target)

A real Nexus run: `validate_goal` (governance, unchanged) → **PLANNING** (model derives a plan *from the
goal*) → loop[ **DECIDING** (model emits a *structured* `ToolCall`) → **TOOL_EXECUTING** (real tool incl.
real search) → observe honest `ToolResult` → persist step+checkpoint+heartbeat (unchanged plumbing) ] →
terminal state (**COMPLETED / FAILED / TIMED_OUT / CANCELLED**) → **real exit status** → persist
artifacts. No mock branch, no canned observation, no always-`0` exit. (`H-1-nexus-master-design.md` Q1;
state machine in `H-1-nexus-lifecycle-design.md` §2.)

## 3. The ten required answers (explicit)

### Q1 — How `AsyncMock` is removed from production paths
- **Delete** `from unittest.mock import AsyncMock` (`nexus.py:7`) and the entire `is_mocked` decision
  block (`nexus.py:198-223`). The production loop keeps **only** the real-model branch
  (`nexus.py:224-246`), upgraded to structured parsing (Q… below).
- **Where the simulation goes:** into **tests**, injected through the *existing constructor seam*. Today
  `NexusRuntimeAdapter.__init__` already accepts `openrouter_client` (`nexus.py:29-42`); tests pass a
  **fake client** (a plain object/`Protocol` impl returning canned completions) instead of an in-module
  `AsyncMock`. A new `SearchProvider` seam (Q2) is injected the same way.
- **No silent downgrade:** with the mock branch gone, a missing/invalid key cannot quietly become canned
  behavior — it surfaces via fail-fast init (P1-3) or a real error. A **guard test** asserts
  `unittest.mock` is not imported by `nexus.py`.
- **Order:** the fake-client + `SearchProvider` test doubles must exist before the branch is deleted, or
  the 4 existing `test_nexus.py` tests (which run through the mock path) break. Sequenced in
  `H-2-implementation-plan.md`.

### Q2 — How real search is introduced via `SearchProvider`
- Define a **`SearchProvider` port** — a minimal protocol `search(query: str) -> list[result]` —
  resolved by **constructor injection**, mirroring `openrouter_client` (Rule 2; `H-1-nexus-tooling-design.md`
  §3). New module e.g. `nexus/execution/runners/search_provider.py` (additive; no schema).
- `_execute_tool`'s `web_search` branch (`nexus.py:84-94`) calls `self.search_provider.search(query)`
  instead of returning canned text. The **canned text becomes a test double** behind the same port,
  relocated to tests (kills Cap 8 "simulated search in prod").
- **Production provider choice is an impl-AP decision** (an HTTP search/retrieval backend, or reuse of
  the OpenRouter-backed `intelligence/research.py` path). H-2 fixes only the **abstraction + injection
  seam**, not the vendor.
- **Egress governance (cross-track, already decided):** real search does network I/O. Per
  `R-05-shared-resolution.md` §6, search egress must obey the active sandbox network policy — under
  `network=none` it runs as an explicitly control-plane-governed (host) action **or** is disabled; never
  a hidden in-container egress (Rule 9). H-2 consumes this rule; Track S owns it.

### Q3 — How goal-derived planning replaces decorative plans
- Remove the hardcoded literal (`nexus.py:159-163`). In **PLANNING**, one model call derives an initial
  plan **from the goal**; it is stored as the existing `agent_plan` artifact (`nexus.py:357-365`,
  unchanged schema) and is **advisory & revisable** — it informs/records intent but never a hardcoded
  script (`H-1-nexus-capability-model.md` Pillar A). The loop may revise it from the trajectory.
- Target tier: Cap 2 Simulated → **Partially Implemented** (Experimental). Advanced dependency-graph
  replanning is **P2**.

### Q4 — How exit status becomes truthful
- `execute_goal` returns an `exit_code`/`status` **derived from the real loop outcome**, not a constant.
  Terminal mapping: genuine `finish` → `0`/COMPLETED; unrecoverable error / `ToolResult.ok=false`
  aggregate → non-zero/FAILED. The current swallow-exception-as-finished path (`nexus.py:254-259`) is
  replaced by a real FAILED transition; failed steps persist with a non-COMPLETED `ExecutionStatus`
  (instead of always `COMPLETED.value`, `nexus.py:269`).
- **No orchestrator change needed for Experimental:** `orchestrator.py:227` already maps
  `exit_code != 0 → ExitStatus.FAILURE`. The new TIMED_OUT/CANCELLED *distinctions* (beyond
  SUCCESS/FAILURE) are **P1** and may add **additive** enum values (impl-AP-decided; no schema redesign).
- Also fix the summary artifact's hardcoded `exit_code: 0` (`nexus.py:385`) to the real value.

### Q5 — How `terminate()` becomes functional (designed; P1)
- **Cooperative cancellation** (`H-1-nexus-lifecycle-design.md` §4): `terminate()` sets a
  **DB-observable** cancel signal on the existing `ExecutionRecord` (no schema redesign — a status/flag
  using existing columns or an additive enum value, impl-AP-decided). The loop checks the signal at
  **state boundaries** (before DECIDING and before TOOL_EXECUTING), bounding latency to one tool
  execution; an in-flight `execute_command` is killed via the **existing** `SandboxProcess.terminate()`
  (`provider.py:47-50`).
- **Wiring (the missing link):** the orchestrator agent branch (`orchestrator.py:210-216`) and the
  timeout path invoke `terminate()` — today they never do. Loop transitions CANCELLING → CANCELLED,
  persists a final checkpoint+audit, returns `cancelled`.
- **Not in H-2's implementation slice** (Experimental); built in **H-4** (lifecycle).

### Q6 — How checkpoint recovery becomes resumable (designed; P1)
- Add `resume_goal(execution_id)` (`H-1-nexus-recovery-design.md` §3): (1) load all `AgentStepRecord`
  rows ordered by `step_index` → rebuild `self.trajectory`; (2) load latest `WorkflowCheckpointRecord`
  for `workflow_id == execution_id` → restore `self.plan` + cursor; (3) `step_index = max+1`; (4)
  re-enter the loop at the **CHECKPOINTED** boundary; re-validate the goal through governance first.
- **Pure read over existing data → no schema change.** Resume **fails closed** on absent/inconsistent
  data (never silently restarts). Mirrors `resume_research_run`/`resume_briefing_run` (one resume idiom,
  Rule 7). Automatic orphan-triggered resume is **P2**; v1.1.0 ships resume as *invocable*.
- **Not in H-2's implementation slice;** built in **H-4** (recovery).

### Q7 — How existing Runtime V2 boundaries remain intact
- **Adapter contract preserved.** Nexus stays an `AgentRuntimeAdapter` (`base.py:84-95`); `validate_goal`
  + `execute_goal` signatures unchanged. `resume_goal` is an **additive** method on the agent adapter
  (default/optional so `CLIRuntimeAdapter`/Gemini/Claude are untouched).
- **Collaborators via injection,** not new framework: `search_provider` joins `openrouter_client` as a
  constructor-injected port (Rule 2) — the same pattern the registry already uses.
- **Registry untouched:** `@runtime_registry.register("nexus")` unchanged; routing
  (`orchestrator.py:143,210-216`) unchanged except the P1 `terminate()` invocation.
- **Single execution chokepoint preserved:** commands keep routing through `SandboxManager`; files keep
  routing through the S-4 confinement seam (Rule 9, no reach-around).

### Q8 — How `AgentStepRecord` compatibility is preserved
- The **same fields** continue to be written every step: `execution_id`, `step_index`, `thought`,
  `tool_name`, `tool_arguments`, `tool_result`, `status`, `last_heartbeat` (`nexus.py:262-273`).
  Structured tool-calls populate `tool_name`/`tool_arguments` from the validated `ToolCall`; honest
  results populate `tool_result` from `ToolResult.output`/`error`. **No column added or removed.**
- The only *value-level* change: failed steps write a non-`COMPLETED` `ExecutionStatus` value (already in
  the enum) instead of always `COMPLETED.value`. This is the **resume system-of-record**
  (`H-1-nexus-recovery-design.md` §2) and stays read-compatible with existing tests/consumers.

### Q9 — How no schema redesign is achieved
- All H-2 (P0) changes are **logic-only**: branch removal, a structured-call validator, a search port, a
  plan-generation call, and a real exit-status computation. No tables, columns, or migrations.
- Designed-through P1/P2 items that *could* imply persistence are constrained to **additive enum values**
  (e.g. a TIMED_OUT/CANCELLED status, a cancel flag) **decided at the implementation AP** — additive, not
  a redesign. Resume is a **read** over existing `agent_steps`/`workflow_checkpoints`. `confinement.py`
  already exists (S-4). Net: **zero migrations** for H-2; additive-only enums if/when P1 lands.

### Q10 — What qualifies Nexus as Experimental after H-2
Per `ADR-nexus-v1.1-foundation` Prototype→Experimental gate, **all** must hold with tests:
1. **No simulation in the prod path** — `AsyncMock`/`is_mocked` removed (P0-1).
2. **Real exit status** — outcome-derived `exit_code`/status; failures finalize FAILURE (P0-4).
3. **Real search** — `SearchProvider` with a real provider; canned = test double (P0-5).
4. **Structured tool-calls** — schema-validated; malformed = explicit error, not silent `finish` (P0-2).
5. **Goal-derived plan** — generated from the goal, advisory, no literal (P0-3).
6. **Real-LLM-branch tests** — coverage of the real decision path, real search, honest failure (P0-6).
AP-105 ledger Caps 2, 3, 4, 8, 18 reclassify ≥ Partially-Implemented with tests. **Lifecycle safety
(terminate/resume) is NOT required for Experimental** — that is the Pilot bar (H-4).

## 4. What is explicitly preserved (do not regress)

Governance-gated `validate_goal`; real `agent_steps`/`checkpoint`/`heartbeat`/`artifact` persistence;
real file (S-4-confined) + command (Track-S-contained) tools; real summarization; registry/contract
integration (AP-105 §4). H-2 changes *intelligence honesty*, not architecture.

## 5. Risks & mitigations (design-level)

| Risk | Mitigation |
|---|---|
| Removing mock branch breaks the 4 mock-path tests | Land fake-client + search-double seams first; convert tests to injection (P0-6 before P0-1) |
| Real search introduces uncontrolled egress | Bind to Track S network policy (`R-05-shared-resolution.md` §6); no hidden path |
| Exit-status change cascades to task finalization | Orchestrator already maps exit_code→status; verify e2e `test_mvp_workflow` still green |
| Structured-call strictness rejects valid model output | Explicit error `ToolResult` + bounded retry (impl detail); never silent `finish` |
| Scope creep into P1/P2 | Gap-prioritization fixes H-2 to the six P0 items; terminate/resume are H-4 |

## 6. Status

Design only. No code, no migration, no commit of implementation. Companion deliverables:
`H-2-gap-prioritization.md`, `H-2-test-strategy.md`, `H-2-implementation-plan.md`. Implementation remains
**gated** pending explicit approval.
