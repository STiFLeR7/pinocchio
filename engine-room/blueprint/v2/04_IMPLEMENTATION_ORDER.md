# Nexus v2 — Implementation Order

Status: Engineering Plan
References: `02_ACTION_POINTS.md`, `03_DEPENDENCY_GRAPH.md`

---

## Purpose

A concrete, topologically valid build order derived from the dependency graph.
It identifies the **critical path**, the **parallel tracks** within each phase,
and the **gate** that must pass before the next phase begins.

This is an ordering, not a schedule. Effort sizes (S/M/L/XL) are in
`02_ACTION_POINTS.md`; convert to dates during phase planning.

---

## Global Critical Path

The longest chain of hard dependencies from first decision to learning loop:

```
AP-001  Persistence model
  ▼
AP-101  Schema format
  ▼
AP-105  Work Package schema        (also needs AP-103 ← AP-102)
  ▼
AP-201  Event bus + store
  ▼
AP-203  State engine
  ▼
AP-303  Context Engineering        (also needs AP-301, AP-302)
  ▼
AP-306  Planning Engine
  ▼
AP-307  Execution Graph Builder
  ▼
AP-401  Orchestration
  ▼
AP-405  Execution
  ▼
AP-502  Validation
  ▼
AP-503  Recovery
  ▼
AP-601  Reflection
  ▼
AP-602  Knowledge
  ▼
AP-603  Knowledge retrieval/feedback  ← end-to-end learning loop closes
```

Protect this path: any slip here slips the whole program. The XL/Critical APs
on it (AP-201, AP-306, AP-401, AP-503) should be split into sub-APs and staffed
first.

---

## Ordered Build Sequence

### Phase 0 — Foundation
**Parallel track A (decisions, independent):** AP-001, AP-002, AP-003, AP-004
**Parallel track B (substrate):** AP-005 → AP-006
**Then:** AP-007 (after AP-002/003/004)
**Gate:** all four ADRs accepted; CI green; contract harness self-tests;
glossary + index correct.

> Sequencing note: start AP-001 first and staff it heaviest — it is the deepest
> root. AP-002/003/004 proceed alongside it.

### Phase 1 — Object Model
**First:** AP-101 (gates everything)
**Parallel fan-out after AP-101:**
- AP-102 → AP-103 → AP-105 (the WP sub-chain)
- AP-104 (Plan + Graph)
- AP-106 (Strategy)
- AP-107 (Skill)
- AP-108 → (with AP-002) Capability
- AP-109 (Resource + Harness)
- AP-110 (Session/Observation/Evidence)
- AP-111 (Artifact)
- AP-112 (Event/Policy/Checkpoint/ValReport/Knowledge)
**Gate:** one schema per object; round-trip tests; every documented seam has a
passing contract test.

### Phase 2 — Substrate
**First:** AP-201 → AP-202 (event + idempotency gate the rest)
**Parallel after AP-201/202:**
- AP-203 (State) → enables AP-204 (Checkpoint)
- AP-205 (Policy)
- AP-206 (Artifact store)
- AP-207 (Harness SDK)
**Gate:** synthetic object driven through state machine with exactly-one-event
per transition; checkpoint write/restore; policy deterministic + simulated;
artifact immutable; reference harness registers + discovered by capability;
idempotency proven under duplicate delivery.

### Phase 3 — Understanding Pipeline
**Track 1 (intent→context):** AP-302 (context harnesses) ∥ AP-301 (intent) →
AP-303 (context engineering)
**Track 2 (capability/skill):** AP-304 → AP-305
**Then (planning core):** AP-306 → AP-307 → AP-308 → AP-309
**Gate:** representative multi-domain goals produce valid acyclic Execution
Graphs of well-formed Work Packages; Planning refuses invalid Context Packages;
decisions explainable. **No runtime invoked.**

### Phase 4 — Execution Coordination
**Parallel start:** AP-401 (orchestration) ∥ AP-403 (runtime adapter SDK +
first adapter) — both depend on AP-207
**Then:** AP-402 (resources) and AP-405 (execution) attach to AP-401/403;
AP-406 (governance gate) into AP-401; AP-404 (more adapters) after AP-403
**Gate:** multi-node graph runs to "waiting validation" across ≥2 adapters; no
execution before gates pass; forced runtime failure pauses (not crash); every
orchestration decision replayable; governance denies + audits a violation.

### Phase 5 — Close the Loop
**Parallel:** AP-501 (supervision) ∥ AP-502 (validation)
**Then:** AP-503 (recovery) after AP-501
**Gate:** failing WP detected → classified → restored → retried within bounds →
recovered or escalated, no context/evidence loss; validation passes/fails from
evidence alone; a runtime "success" with insufficient evidence does not
complete; pause/resume/escalate each have exactly one owner.

### Phase 6 — Learn & Mature
**Linear core:** AP-601 → AP-602 → AP-603
**Parallel late:** AP-604 (observability/audit/performance)
**Gate:** a second run of a goal class measurably reuses validated knowledge;
only validated outcomes enter Knowledge; reflections evidence-sourced; full
observability/audit; performance + recoverability targets met under load.

---

## Parallelization Summary

| Phase | Max useful parallel tracks | Serializing bottleneck |
|-------|----------------------------|------------------------|
| 0 | 4 (the four ADRs) + scaffold | AP-007 waits on ADRs |
| 1 | ~9 after AP-101 | AP-101 first; AP-105 sub-chain |
| 2 | ~4 after AP-201/202 | AP-201 → AP-202 |
| 3 | 2–3 tracks | AP-306 → AP-307 → AP-309 core |
| 4 | 2 (orchestration ∥ adapters) | AP-401 hub |
| 5 | 2 (supervision ∥ validation) | AP-503 last |
| 6 | core linear + AP-604 aside | AP-601→602→603 |

---

## Staffing Guidance

- **One owner per XL/Critical AP** (AP-001, AP-201, AP-306, AP-401, AP-503),
  with the AP split into sub-APs at phase-planning time.
- **Schema work (Phase 1) parallelizes widely** — many engineers can own one
  object schema each after AP-101 lands.
- **Harness work is reusable leverage:** invest in AP-207 quality; AP-302/403
  and later validation/communication harnesses all inherit from it.
- **Do not start a pipeline AP whose schema (Phase 1) or substrate (Phase 2)
  dependency has not passed its contract/gate test** — the contract harness
  (AP-006) is the enforcement mechanism.
