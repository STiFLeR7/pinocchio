# H-2 — Gap Prioritization & Implementation Inventory (Track H)

> **Design only — no implementation.** The precise, evidence-bound inventory of every Nexus gap from
> AP-105, each classified **P0 (required for Experimental) / P1 (required for Pilot) / P2 (future)**,
> with root cause, files impacted, complexity, required tests, architectural risk, and inter-gap
> dependency. Sources: `nexus-reality-audit.md`, `nexus-gap-analysis.md`, `nexus-capability-ledger.md`,
> `ADR-nexus-v1.1-foundation.md`, `H-1-*` sub-designs, and current source re-read at commit `b734c13`.

---

## 0. Two reality updates since AP-105 (verified in source at `b734c13`)

| Item | AP-105 state | Now (after Track S / S-4) |
|---|---|---|
| **R-05 / Gap 7** file-tool host bypass | Open | **Closed at floor** — `nexus.py:96-117` routes `read_file`/`write_file` through `resolve_in_workspace` (S-4). Only the in-container *ceiling* remains (deferred). |
| **Exit-status wiring** | Assumed needs orchestrator change | Orchestrator **already** maps `exit_code != 0 → ExitStatus.FAILURE` (`orchestrator.py:227`). Honesty is a **Nexus-side** fix (return a real `exit_code`); orchestrator change only needed for *new terminal distinctions* (TIMED_OUT/CANCELLED), which is additive and Pilot-tier. |

These reduce H-2's blast radius: file confinement is done, and exit-status honesty needs no orchestrator
edit for the Experimental bar.

## 1. Priority definitions

| Priority | Meaning | Promotion gate (`ADR-nexus-v1.1-foundation`) |
|---|---|---|
| **P0** | Required for **Prototype → Experimental** | No prod mock · real exit status · real search · structured tool-calls · goal-derived plan · real-LLM-branch tests |
| **P1** | Required for **Experimental → Pilot** | P0 + wired/tested cancellation · working/tested resume · R-05 file confinement · fail-fast init · configurable budget · one audited real run |
| **P2** | Future / beyond v1.1.0 Pilot | Deferred list (master-design §7, Q10) + R-05 ceiling + auto-resume trigger |

## 2. P0 inventory — required for Experimental (the H-2 implementation target)

### P0-1 — Remove `AsyncMock` + `is_mocked` branch from the production path
- **Maps to:** Gap 2 (🔴), Cap 4 (Mocked → Not-Present-in-prod). Audit Q1.
- **Root cause:** `from unittest.mock import AsyncMock` (`nexus.py:7`) and the `is_mocked` decision block
  (`nexus.py:198-223`) place test scaffolding in the runtime; a missing/`"test-key"` key silently
  downgrades to canned decisions with no signal.
- **Files impacted:** `nexus/execution/runners/nexus.py` (remove import + branch); `tests/unit/execution/test_nexus.py` (relocate simulation into an injected fake).
- **Complexity:** Medium — the mock branch currently *is* the test path; removing it requires the test
  fake (P0-2 seam) to land first.
- **Required tests:** real-LLM-branch test using an injected fake `openrouter_client` (not `AsyncMock`
  inside the module); assert no `unittest.mock` import remains in `nexus.py` (guard test).
- **Architectural risk:** Medium — `test_nexus.py` runs entirely through the mock path today; naive
  removal breaks 4 tests. Mitigated by injecting the fake via the existing constructor seam.
- **Depends on:** P0-2 (structured tool-call seam) and P0-5 (search port) for the injected fakes.

### P0-2 — Structured, schema-validated tool-call contract (no silent `finish`)
- **Maps to:** Gap 6 (🟠), Cap 3 (Partially → Implemented). Audit Q on parsing.
- **Root cause:** free-text completion parsed by string-splitting code fences + `json.loads` with a
  keyword fallback that defaults to `finish` (`nexus.py:224-246`); malformed output ends the run as a
  fake completion.
- **Files impacted:** `nexus.py` (`_parse_tool_call`/decision section); new small contract type (a
  Pydantic model or TypedDict for `ToolCall`/`ToolResult`, per `H-1-nexus-tooling-design.md` §2) — a
  new module e.g. `nexus/execution/runners/nexus_tools.py` (additive, no schema).
- **Complexity:** Medium — validation + an explicit parse-failure → error `ToolResult` path.
- **Required tests:** valid structured call parsed; malformed call → explicit error state (not `finish`);
  unknown tool name → error `ToolResult`.
- **Architectural risk:** Low — internal to the adapter; no contract/registry change.
- **Depends on:** none (foundation for P0-1, P0-3, P0-4).

### P0-3 — Goal-derived planning (replace the decorative literal)
- **Maps to:** Gap 1a (🔴), Cap 2 (Simulated → Partially Implemented). Audit Q1/Q3.
- **Root cause:** hardcoded 3-step literal identical for any goal, never drives the loop
  (`nexus.py:159-163`).
- **Files impacted:** `nexus.py` (`execute_goal` plan formulation; plan becomes a model-generated,
  advisory artifact). Persists via existing `agent_plan` artifact (`nexus.py:357-365`) — unchanged
  schema.
- **Complexity:** Medium — one model call to derive the plan from the goal; plan stays advisory/revisable.
- **Required tests:** plan is derived from the goal (varies by goal, not a fixed literal); plan persists
  as a real `agent_plan` artifact; loop runs without the literal.
- **Architectural risk:** Low — artifact persistence already exists; this only changes plan *content*.
- **Depends on:** P0-1 (real model branch).

### P0-4 — Real exit-status fidelity
- **Maps to:** Gap 3 (🔴), Cap 18 (Simulated → Implemented). Audit Q.
- **Root cause:** `execute_goal` returns `exit_code: 0` unconditionally (`nexus.py:296-301`); in-loop
  exceptions set `finished=True` and are recorded as a completed step (`nexus.py:254-259`).
- **Files impacted:** `nexus.py` (`execute_goal` return; per-step `status` for failed steps; summary
  artifact `exit_code` at `nexus.py:385`). **Orchestrator unchanged** for the Experimental bar (it
  already maps `exit_code → FAILURE`, `orchestrator.py:227`).
- **Complexity:** Low–Medium — derive `exit_code`/`status` from real loop outcome
  (completed/failed); mark failed steps with a non-COMPLETED `ExecutionStatus`.
- **Required tests:** a tool/loop failure yields non-zero `exit_code` and a FAILED finalization; a genuine
  `finish` yields `exit_code 0`; failed step persisted with truthful `status`.
- **Architectural risk:** Low — uses existing `ExecutionStatus` values; SUCCESS/FAILURE already wired.
- **Depends on:** P0-2 (honest `ToolResult.ok`).

### P0-5 — Real search via `SearchProvider` port
- **Maps to:** Gap 1b (🔴), Cap 8 (Simulated → Implemented). Audit Q3/Q4.
- **Root cause:** `web_search` returns canned text in both branches (`nexus.py:84-94`); no provider call.
- **Files impacted:** new `SearchProvider` protocol + injection seam (constructor, mirroring
  `openrouter_client`) — e.g. `nexus/execution/runners/search_provider.py`; `nexus.py` (`__init__`
  signature additive param; `_execute_tool` `web_search` calls the port); `test_nexus.py` (canned
  response becomes an injected **test double**). Production provider choice is an **impl-AP decision**;
  H-2 fixes only the abstraction + injection seam.
- **Complexity:** Medium — port + injection + the canned→test-double relocation; **network egress must
  obey the active sandbox policy** (`R-05-shared-resolution.md` §6 — Track S owns the egress rule).
- **Required tests:** real provider path invoked (fake provider returns deterministic results); canned
  text absent from the runtime; egress-policy guard (search disabled/host-governed under `network=none`).
- **Architectural risk:** Medium — introduces network I/O; bounded by the cross-track egress decision
  (no hidden network path, Rule 9).
- **Depends on:** Track S network-policy rule (already specified in `R-05-shared-resolution.md` §6).

### P0-6 — Real-LLM-branch test coverage (honesty evidence)
- **Maps to:** Gap 9 (🟡, P0 portion). Audit Q.
- **Root cause:** `test_nexus.py` runs entirely through the mock path; green tests don't evidence
  autonomous behavior.
- **Files impacted:** `tests/unit/execution/test_nexus.py` (+ possibly a new test module).
- **Complexity:** Medium — fixtures injecting fake LLM + fake search providers.
- **Required tests:** see P0-1…P0-5 "required tests"; this gap is the umbrella that they satisfy.
- **Architectural risk:** Low.
- **Depends on:** P0-1, P0-2, P0-5 seams.

## 3. P1 inventory — required for Pilot (designed by H-2, implemented in later gated APs)

### P1-1 — Functional + wired cooperative `terminate()`
- **Maps to:** Gap 5 (🟠), Cap 14 (Not Present → Implemented). Audit Q7. `H-1-nexus-lifecycle-design.md` §4.
- **Root cause:** `terminate()` is `pass` (`nexus.py:324-326`) and the orchestrator agent branch never
  calls it (`orchestrator.py:210-216`).
- **Files impacted:** `nexus.py` (cancel signal + loop-boundary checks + in-flight `SandboxProcess`
  kill); `orchestrator.py` (invoke `terminate()` on timeout/operator action — the missing wiring).
- **Complexity:** Medium–High — cooperative cancellation + DB-observable signal + orchestrator wiring.
- **Required tests:** cancel between steps → `CANCELLED` terminal + `cancelled` exit; in-flight command
  killed; latency bounded to one tool execution.
- **Architectural risk:** Medium — touches the orchestrator (kept minimal: one invocation point); reuses
  existing `SandboxProcess.terminate()` (`provider.py:47-50`), no new mechanism.
- **Depends on:** P0-4 (terminal-status model), lifecycle state machine.

### P1-2 — `resume_goal` (resumable checkpoint recovery)
- **Maps to:** Gap 4 (🟠), Cap 12 (Not Present → Implemented). Audit Q5/Q7. `H-1-nexus-recovery-design.md`.
- **Root cause:** checkpoints write-only; `execute_goal` always restarts (`nexus.py:148-156`); no
  `resume_goal` (only `research.py`/`briefing.py` resume).
- **Files impacted:** `nexus.py` (new `resume_goal(execution_id)` reading `agent_steps` + latest
  `WorkflowCheckpointRecord`); `base.py` (`AgentRuntimeAdapter` — additive method, default/optional to
  preserve CLI adapters); optional orchestrator/operator caller (invocable, not auto).
- **Complexity:** Medium — pure read-reconstruction over existing data; mirrors `resume_research_run`.
- **Required tests:** resume rebuilds trajectory from steps; continues from cursor; no duplicate step;
  absent/inconsistent data → fail-closed; governance re-validated on resume.
- **Architectural risk:** Low — read over existing schema; no migration; mirrors existing resume idiom.
- **Depends on:** P0-4 (terminal-state semantics define resumable boundary).

### P1-3 — Fail-fast initialization
- **Maps to:** Gap 8a (🟡), Cap 17 (Stubbed → Implemented). `ADR` Pilot gate.
- **Root cause:** `initialize()` checks for a key then `pass` if absent (`nexus.py:48-56`).
- **Files impacted:** `nexus.py` (`initialize` raises on missing usable key).
- **Complexity:** Low.
- **Required tests:** missing key → fail-fast (raises, run does not proceed); present key → proceeds.
- **Architectural risk:** Low.
- **Depends on:** P0-1 (no mock fallback to mask a missing key).

### P1-4 — Configurable step budget + `TIMED_OUT` enforcement
- **Maps to:** Gap 8b (🟡), Cap 19 (hardcoded `max_steps=5` → configurable). Lifecycle §5.
- **Root cause:** `max_steps = 5` hardcoded (`nexus.py:165`); budget exhaustion silently reports success.
- **Files impacted:** `nexus.py` (read budget from config; budget/wall-clock exhaustion → `TIMED_OUT`);
  config (additive field).
- **Complexity:** Low–Medium.
- **Required tests:** budget exhaustion → `TIMED_OUT` (distinct from COMPLETED); configurable value honored.
- **Architectural risk:** Low–Medium — `TIMED_OUT` may need an additive `ExitStatus`/`ExecutionStatus`
  value (additive enum, impl-AP-decided; **no schema redesign**).
- **Depends on:** P0-4.

### P1-5 — Pilot test depth (cancellation + resume + one audited real run)
- **Maps to:** Gap 9 (Pilot portion). `ADR` Pilot gate.
- **Files impacted:** `test_nexus.py` / new tests.
- **Complexity:** Medium.
- **Depends on:** P1-1, P1-2.

> **R-05 file confinement (Gap 7 floor):** **already delivered by S-4** (`nexus.py:96-117`). Listed here
> as a **Pilot requirement satisfied early** — no H-2/H-x work needed for the floor.

## 4. P2 inventory — future (beyond v1.1.0 Pilot)

| Item | Source | Why deferred |
|---|---|---|
| In-container file I/O ceiling (R-05) | `R-05-shared-resolution.md` §3 | Floor already prevents escape; defense-in-depth only |
| Automatic orphan-detection → resume trigger | `H-1-nexus-recovery-design.md` §5 | Needs orphan-execution monitor (scheduler concern); v1.1.0 ships resume as *invocable* |
| Advanced replanning / dependency-graph planning | master-design §7 | Beyond advisory planning |
| New tools beyond the existing five | capability-model §3 | Scope guard |
| Non-OpenRouter model backends, per-step Discord streaming | master-design Q10 | Deferred |
| Dedicated `AGENT_*`/`EXECUTION_*` event taxonomy | lifecycle §6 | Impl-AP decision; not required for honest finalization |
| Production Ready status | ADR §Consequences | Explicitly not a v1.1.0 goal |

## 5. Dependency graph (P0/P1)

```
P0-2 structured tool-calls ─┬─► P0-1 mock removal ─► P0-3 goal-derived plan
                            ├─► P0-4 exit status ──► P1-1 terminate
P0-5 search port ───────────┘                   └─► P1-4 budget/TIMED_OUT
P0-4 ──► P1-2 resume_goal
P0-1 ──► P1-3 fail-fast init
(P0-1,P0-2,P0-5) ──► P0-6 real-branch tests
S-4 (done) ──► R-05 floor [CLOSED]
```

**Critical path for Experimental:** P0-2 → P0-1 → {P0-3, P0-4, P0-5} → P0-6.

## 6. Summary counts

| Priority | Count | Items |
|---|---|---|
| **P0 (Experimental)** | 6 | mock removal, structured calls, goal-derived plan, exit status, search port, real-branch tests |
| **P1 (Pilot)** | 5 (+R-05 floor done) | terminate, resume, fail-fast init, configurable budget/TIMED_OUT, Pilot tests |
| **P2 (Future)** | 7 | R-05 ceiling, auto-resume, advanced planning, new tools, backends/streaming, event taxonomy, Production Ready |

**H-2 implementation scope (when authorized): the six P0 items → Experimental.** P1/P2 are designed here
but implemented in later, separately-gated APs (H-3…H-5).
