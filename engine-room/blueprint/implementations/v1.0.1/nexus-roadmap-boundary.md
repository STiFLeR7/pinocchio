# Nexus Roadmap Boundary (AP-105)

> Draws a hard line between **current repository reality** (what AP-105 audited and certified) and
> **roadmap / future work** (explicitly out of this audit's scope). Its purpose is to prevent roadmap
> language from leaking back into status claims — the same drift A-004 corrected. **No work is proposed
> or authorized here.**

---

## 1. The boundary, stated plainly

| Side of the line | What belongs here |
|---|---|
| **Reality (this audit)** | What Nexus *is*, by evidence, today — the ledger, trace, gaps, and verdict. |
| **Roadmap (NOT this audit)** | How to fix Nexus, in what order, with what design — a *future* Action Point if/when authorized. |

AP-105 lives entirely on the **Reality** side. Everything below the next heading is a *catalogue* of
where future work would go, not a plan, schedule, or commitment.

## 2. Reality (certified by AP-105)

- Nexus is a **Prototype** (Concept Demonstration in default config). Verdict and evidence in
  `nexus-reality-audit.md` §5.
- Real: governance validation, agent-step/checkpoint/heartbeat/artifact persistence, file + command
  tool execution, summarization, registry/contract integration, real LLM action loop in prod config.
- Simulated/absent: dynamic planning, web search, honest exit status, termination, resume, plus an
  in-module `AsyncMock`.
- Full classification: `nexus-capability-ledger.md`. Trace: `nexus-execution-trace-analysis.md`.
  Gaps: `nexus-gap-analysis.md`.

## 3. Roadmap catalogue (future Action Point territory — descriptive only)

These map 1:1 to the ledger's "Required Work" but are **not** scheduled, designed, or approved by AP-105:

| Theme | Future-work pointer (no design implied) | Source gap |
|---|---|---|
| Honest intelligence | Real search provider; goal-derived planning that drives the loop; remove prod mock | Gaps 1, 2 |
| Honest outcomes | Real exit-status propagation; structured tool-call parsing | Gaps 3, 6 |
| Lifecycle safety | Resume-from-checkpoint; cooperative termination wired to orchestrator/timeout | Gaps 4, 5 |
| Hardening | Path-confined file tools (+ A-006 sandbox); fail-fast init; configurable step budget | Gaps 7, 8 |
| Test depth | Cover real-LLM branch, termination, resume | Gap 9 |

## 4. Explicit non-actions (scope guard)

AP-105 did **not**, and the boundary forbids within this AP:
- Modifying `nexus.py` or any source.
- Removing the `AsyncMock` import (a code change — recorded as a gap, not fixed).
- Designing or implementing search, planning, resume, or termination.
- Re-classifying Nexus upward based on intended future capability.
- Editing documentation to describe Nexus as more than a Prototype.

## 5. How this protects the blueprint

A-004 corrected docs that described unbuilt things as built. The inverse risk for Nexus is describing a
**Prototype** as a functional agent runtime because the *roadmap* says it will be. This boundary
document is the standing guard: **until a future implementation AP changes the evidence, Nexus is a
Prototype**, and `architecture-status-summary.md` must keep classifying it **Mocked (partial) /
Prototype**. Any upgrade to its status requires new code + new evidence, not new intentions.

## 6. Dependencies to note (not owned by Nexus)

- **A-006 (Sandbox Safety Review)** gates the honesty of `execute_command` isolation — Nexus hardening
  (Gap 7) cannot be fully resolved before A-006.
- **Orphan-execution monitor** (audit 09 / continuous-operation gap) would give heartbeat (Cap 13) a
  consumer; it is a scheduler/recovery concern, not a Nexus-internal one.
