# Nexus v2 — Implementation Blueprint

This directory is the authoritative engineering roadmap for implementing the
Nexus v2 target architecture defined in `docs/v2/`.

It is a **planning workspace**, not source code. No production code,
placeholder code, speculative APIs, or invented schemas live here — only the
disciplined plan to build them.

> This is a new, parallel planning space. It does **not** modify the existing
> `blueprint/` content.

---

## Read in This Order

| # | Document | Purpose |
|---|----------|---------|
| — | `00_IMPLEMENTATION_OVERVIEW.md` | Start here. Architecture in brief + how to use this directory. |
| 1 | `01_PHASES.md` | The six engineering phases and their validation gates. |
| 2 | `02_ACTION_POINTS.md` | The authoritative Action Point catalog (the unit of work). |
| 3 | `03_DEPENDENCY_GRAPH.md` | Layer and Action-Point dependency graphs. |
| 4 | `04_IMPLEMENTATION_ORDER.md` | Topological build order, critical path, parallel tracks. |
| 5 | `05_RISKS.md` | Ranked risk register with mitigations. |
| 6 | `06_TECHNICAL_DEBT.md` | Deliberate shortcuts and repayment plan. |
| 7 | `07_UNKNOWNS.md` | Decisions the architecture intentionally leaves open. |
| 8 | `08_ARCHITECTURE_GAPS.md` | Contradictions/gaps found during absorption + resolutions. |
| 9 | `09_ADR_BACKLOG.md` | Architecture Decision Records that must exist before/early in build. |
| 10 | `10_VALIDATION_STRATEGY.md` | Per-phase validation gates and acceptance evidence. |
| 11 | `11_TESTING_STRATEGY.md` | Unit/integration/contract/failure/recovery testing per subsystem. |
| 12 | `12_ROADMAP.md` | Phase sequencing into a delivery arc with milestones. |

---

## The Spine

- **Phases** describe *when* capability is built and *what gate* proves it.
- **Action Points** describe *what* to build, with dependencies, acceptance
  criteria, and validation per unit.
- Everything else (dependency graph, order, risks, ADRs, validation, testing,
  roadmap) references the **stable AP identifiers** in `02_ACTION_POINTS.md`.

AP identifiers (`AP-PNN`) are stable. Never renumber — deprecate and supersede.

---

## Principles for This Blueprint

- **No implementation.** Plans only. No code, schemas, protocols, or DB designs
  invented here.
- **One responsibility per layer.** The blueprint preserves the architecture's
  boundaries; it never merges responsibilities to simplify a plan.
- **Evidence over assertion.** Every phase ends at a validation gate; nothing is
  "done" without gate evidence.
- **Decisions before dependencies.** Architectural unknowns are resolved (ADRs)
  before the work that depends on them.

---

## Source Architecture Status

The `docs/v2/` set is structurally complete (00–26 + README). Three documents
that were empty/duplicated during absorption — Supervision (09), Harness (11),
Reflection (26) — are now specified. Remaining work is reconciliation, tracked
in `08_ARCHITECTURE_GAPS.md` and the Phase-0 Action Points.
