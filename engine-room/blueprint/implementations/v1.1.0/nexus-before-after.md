# Nexus — Before vs After (H-2 Honesty)

> Side-by-side of the Nexus runtime before H-2 (Prototype) and after (Experimental). Behavioral claims
> re-verified against current source + the H-2 suite (194 passed, ruff/mypy clean). Review only.

---

## 1. Decision path

| Aspect | Before (Prototype) | After (Experimental) |
|---|---|---|
| Branching | `is_mocked` branch chose canned decisions when no/`"test-key"` key (`nexus.py:198-223`) | **Single real path**: `model.complete → parse_tool_call → ToolCall` |
| Test scaffolding in runtime | `from unittest.mock import AsyncMock` (`nexus.py:7`) | **Removed**; simulation only in injected test doubles |
| Malformed model output | string-split + keyword fallback → silent `finish` (`nexus.py:224-246`) | `ToolCallParseError` → **explicit FAILED**, never silent finish |
| Missing key | silently downgraded to canned behavior | honest failure (no mock fallback) |

## 2. Search

| Aspect | Before | After |
|---|---|---|
| `web_search` | canned MCP text in both branches (`nexus.py:84-94`) | `self.search_provider.search(query)` — provider-backed |
| No provider configured | n/a (always canned) | honest error: "no search provider is configured…" (no canned text) |
| Abstraction | none | `SearchProvider` ABC, constructor-injected (Rule 2) |
| Canned text | in runtime | demoted to a **test double** in `tests/` |

## 3. Planning

| Aspect | Before | After |
|---|---|---|
| Plan source | hardcoded 3-step MCP literal, goal-independent (`nexus.py:159-163`) | `_generate_plan(goal)` — model/goal-derived |
| Goal sensitivity | none | plan reflects the goal (or goal-derived fallback) |
| Literal present | yes | **removed** (guard-tested) |

## 4. Outcomes / exit status

| Aspect | Before | After |
|---|---|---|
| Return | `{"exit_code": 0, …}` unconditionally (`nexus.py:284-289`) | `{"exit_code": 0 or 1, "status": "completed"/"failed", …}` outcome-derived |
| In-loop exception | set `finished=True`, recorded as completed | recorded as **FAILED** step, `exit_code 1` |
| Budget exhausted w/o finish | reported success | reported **failed/incomplete** (`exit_code 1`) |
| Failed step status | always `COMPLETED` | `ExecutionStatus.FAILED` (existing enum value) |
| Orchestrator finalization | always SUCCESS (exit 0) | FAILURE on real failure (orchestrator unchanged; already maps exit_code) |
| Summary artifact `exit_code` | hardcoded 0 | real `self.exit_code` |

## 5. Preserved (unchanged — do not regress)

| Aspect | State |
|---|---|
| Governance gate (`validate_goal` → `GovernanceManager`) | unchanged |
| `AgentStepRecord` schema + fields written | unchanged (only failed-step `status` *value* differs) |
| Checkpoint / heartbeat / artifact persistence | unchanged plumbing |
| File tools workspace confinement (S-4) | unchanged |
| `execute_command` sandbox containment (Track S) | unchanged |
| `AgentRuntimeAdapter` contract, RuntimeRegistry | unchanged |
| Orchestrator architecture | unchanged |
| Schema / migrations | none |

## 6. Net classification movement

| | Before | After |
|---|---|---|
| Verdict | **Prototype** | **Experimental** |
| Simulated-in-prod capabilities | 5 (mock, search, planning, parse, exit) | **0** |
| Pilot-gating capabilities open | 4 (terminate, resume, init, budget) | 4 (unchanged — deferred to H-4) |
| Tests | 178 | **194 (+16)** |

## 7. Runtime traces (recorded)

```
SUCCESS : plan=['Research the topic','Report findings']  step0 web_search(completed)  step1 finish(completed)  -> exit 0/completed
FAILURE : step0 error(failed) 'model transport failure'                                                       -> exit 1/failed
MALFORMED: step0 error(failed) 'Tool-call parse error: ...'                                                    -> exit 1/failed
```

## 8. One-line summary

Nexus moved from **"canned decisions, fake search, decorative plan, always-success"** to
**"real model decisions via structured tool-calls, provider-backed search, goal-derived planning, and
truthful success/failure outcomes"** — honest (Experimental), with lifecycle safety (terminate/resume)
still ahead at Pilot/H-4.
