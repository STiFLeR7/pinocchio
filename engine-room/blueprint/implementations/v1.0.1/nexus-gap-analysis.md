# Nexus Gap Analysis (AP-105)

> The delta between what Nexus **claims/appears** to do and what it **actually** does, organized by
> theme with severity and the (descriptive only) work that would close each gap. Audit-only — no fixes
> proposed for implementation here.

---

## Severity scale
🔴 Critical (dishonest/unsafe in a governed system) · 🟠 High (core agent integrity) · 🟡 Medium · 🟢 Low.

---

## Gap 1 — Simulated intelligence presented as autonomy 🔴

| | |
|---|---|
| **Appears** | An autonomous research/planning agent that searches the web and plans. |
| **Reality** | `web_search` returns canned text (`nexus.py:76-86`); the plan is a hardcoded literal (`nexus.py:147-151`); in default config the entire decision sequence is hardcoded (`nexus.py:193-211`). |
| **Impact** | A governed operator could approve a "research" run and receive fabricated findings believed to be real. |
| **Closes when** | Real search provider integrated; plan generated from goal and used to drive the loop; mock branch removed from prod. |

## Gap 2 — Test scaffolding in the production module 🔴

| | |
|---|---|
| **Appears** | A clean production runtime. |
| **Reality** | `from unittest.mock import AsyncMock` at module top (`nexus.py:7`); `is_mocked` branch in the live `execute_goal` (`nexus.py:186-211`). |
| **Impact** | Production behavior depends on a test library; a misconfiguration (missing key, `"test-key"`) silently downgrades to canned behavior with no signal. |
| **Closes when** | `AsyncMock` and the simulation branch are removed from prod and relocated to tests/fixtures. |

## Gap 3 — Failure invisibility 🔴

| | |
|---|---|
| **Appears** | Success/failure is reported. |
| **Reality** | `execute_goal` returns `exit_code: 0` unconditionally (`nexus.py:284-289`); even an in-loop exception sets `finished=True` and is recorded as a completed step (`nexus.py:242-247`), then the orchestrator finalizes `SUCCESS` (`orchestrator.py:227`). |
| **Impact** | Failed agent runs are indistinguishable from successful ones in task state and audit. |
| **Closes when** | Real exit status derived from loop outcome and propagated. |

## Gap 4 — False recoverability 🟠

| | |
|---|---|
| **Appears** | Resumable — checkpoints are written every step. |
| **Reality** | Checkpoints are write-only; `execute_goal` always restarts fresh (`nexus.py:138-139`); no `resume_goal` for the agent path (only `research.py:361`/`briefing.py:250`). |
| **Impact** | An interrupted Nexus run restarts from zero; the checkpoint table implies a capability that does not exist. |
| **Closes when** | A resume path reads the latest checkpoint/steps and continues. |

## Gap 5 — No cancellation 🟠

| | |
|---|---|
| **Appears** | A `terminate()` method exists on the contract. |
| **Reality** | `terminate()` is `pass` (`nexus.py:312-314`) and is never invoked by the orchestrator's agent branch (CLI runners *do* call it, `claude.py:124`). |
| **Impact** | A looping or long-running agent cannot be stopped; no operator kill-switch. |
| **Closes when** | Cooperative cancellation is implemented and invoked on timeout/operator action. |

## Gap 6 — Brittle action parsing 🟠

| | |
|---|---|
| **Appears** | Structured tool-calling. |
| **Reality** | Free-text LLM completion parsed by string-splitting code fences + `json.loads`, with a keyword-heuristic fallback that defaults to `finish` (`nexus.py:213-234`). |
| **Impact** | Malformed model output silently ends the run as "finished" → masquerades as completion. |
| **Closes when** | Schema-validated/structured tool-call output is enforced. |

## Gap 7 — Unconfined tool side effects 🟡

| | |
|---|---|
| **Appears** | Sandboxed execution. |
| **Reality** | `read_file`/`write_file` use raw host FS with no path confinement (`nexus.py:88-105`); `execute_command` uses the sandbox but the default sandbox is `local` = no isolation (A-006, `config.py:133-137`). |
| **Impact** | Agent can read/write arbitrary host paths; command isolation depends on the unaddressed A-006. |
| **Closes when** | Path confinement + A-006 resolution. |

## Gap 8 — Stub initialization & hardcoded bounds 🟡

| | |
|---|---|
| **Appears** | Initialization validates readiness. |
| **Reality** | `initialize()` checks for a key then `pass` if absent (`nexus.py:47-55`); `max_steps=5` hardcoded (`nexus.py:153`). |
| **Impact** | Runs proceed without a usable LLM key; step budget not operator-tunable. |
| **Closes when** | Fail-fast on missing key; configurable step budget. |

## Gap 9 — Tests prove plumbing, not autonomy 🟡

| | |
|---|---|
| **Appears** | Nexus is tested (4 tests). |
| **Reality** | `test_nexus.py` runs entirely through the **mock** path; it asserts persistence/governance/artifact shape, never real LLM reasoning, real search, termination, or resume. |
| **Impact** | Green tests do not evidence the autonomous behaviors Nexus advertises. |
| **Closes when** | Tests cover the real LLM branch (mocked transport, not mocked decisions), termination, and resume. |

---

## Gap summary

| Severity | Gaps |
|---|---|
| 🔴 Critical | Simulated intelligence (1), prod test-mock (2), failure invisibility (3) |
| 🟠 High | False recoverability (4), no cancellation (5), brittle parsing (6) |
| 🟡 Medium | Unconfined side effects (7), stub init/bounds (8), shallow tests (9) |

**The architecture is not the gap** — the registry/contract/persistence layer is sound. The gaps are
**intelligence honesty** (1,2,3,6) and **lifecycle safety** (4,5), with secondary hardening (7,8,9).
Sequencing of any remediation is deliberately out of scope (see `nexus-roadmap-boundary.md`).
