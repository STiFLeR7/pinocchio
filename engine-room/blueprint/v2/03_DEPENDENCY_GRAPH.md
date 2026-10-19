# Nexus v2 — Dependency Graph

Status: Engineering Plan
References: `01_PHASES.md`, `02_ACTION_POINTS.md`

---

## Purpose

This document makes every implementation dependency explicit at two
resolutions: the **layer dependency graph** (architectural) and the **Action
Point dependency graph** (implementation). It is the basis for
`04_IMPLEMENTATION_ORDER.md`.

Two rules hold throughout:
- **Architectural flow is one-way.** Higher layers understand work; lower
  layers execute it; lower layers never influence higher-level decisions.
- **Implementation flow has no cycles.** Every AP depends only on APs that can
  be completed before it. Any apparent cycle is a modeling error to be removed,
  not scheduled around.

---

## Layer Dependency Graph (architectural)

```
                 ┌─────────────────────────────────────────────┐
                 │            CROSS-CUTTING SUBSTRATE           │
                 │  Object Model · Event · State · Checkpoint   │
                 │  Policy Engine · Capability · Resource ·     │
                 │  Runtime · Artifact · Governance · Harness   │
                 └─────────────────────────────────────────────┘
                        ▲ every pipeline layer consumes substrate ▲

 Operator
   │
   ▼
 Intent Resolution ──► Context Engineering ──► Planning ──► Execution Strategy
                                                  │                │
                                                  ▼                ▼
                                            Skill Selection    Work Packaging
                                                  └──────┬─────────┘
                                                         ▼
                                                   Orchestration
                                                         ▼
                                                     Execution
                                                         ▼
                                                    Supervision ──► (recommends)
                                                         ▼            Orchestration acts
                                                     Validation
                                                         ▼
                                                      Recovery ──► (restores) Orchestration
                                                         ▼
                                                     Reflection
                                                         ▼
                                                     Knowledge ──► (feeds) Context + Planning
```

**Feedback edges are indirect and controlled** (not violations of one-way flow):
- Supervision → Orchestration: *recommendations only* (Orchestration owns control).
- Recovery → Orchestration: *restore/resume coordination*.
- Knowledge → Context/Planning: *retrieval only* (Planning never depends on
  Reflection directly; only on persisted, validated Knowledge).

---

## Phase Dependency Graph

```
Phase 0 ──► Phase 1 ──► Phase 2 ──► Phase 3 ──► Phase 4 ──► Phase 5 ──► Phase 6
(decisions) (schemas)  (substrate) (understand) (execute)  (close loop) (learn)
```

No phase depends on a later phase. Phase 2 (substrate) is built before the
pipeline phases (3–6) consume it. Phase 3 has no runtime dependency and can be
validated entirely on Phases 1–2.

---

## Action Point Dependency Graph

Notation: `AP-X ← AP-Y` means AP-X depends on AP-Y (Y before X).

### Phase 0 (no internal hard cycle; AP-007 last)
```
AP-001  Persistence model            ← (none)
AP-002  Registry unification         ← (none)
AP-003  Object reconciliation        ← (none)
AP-004  Policy/approval/determinism  ← (none)
AP-005  Scaffold + CI                ← (none)
AP-006  Contract-test harness        ← AP-005
AP-007  Glossary + index repair      ← AP-002, AP-003, AP-004
```
AP-001…AP-005 are independent and parallelizable. AP-006 waits on AP-005.
AP-007 waits on the three reconciliation ADRs.

### Phase 1 (schemas)
```
AP-101  Schema format/identity/ver   ← AP-001, AP-003
AP-102  Goal                         ← AP-101, AP-003
AP-103  Context Package              ← AP-101, AP-102
AP-104  Plan + Execution Graph       ← AP-101, AP-003
AP-105  Work Package (unified)       ← AP-101, AP-103, AP-003
AP-106  Execution Strategy           ← AP-101, AP-004
AP-107  Skill + registry             ← AP-101
AP-108  Capability + registry        ← AP-101, AP-002
AP-109  Resource + Harness           ← AP-101, AP-002, AP-003
AP-110  Session/Observation/Evidence ← AP-101, AP-003
AP-111  Artifact + lineage           ← AP-101
AP-112  Event/Policy/Checkpoint/      ← AP-101, AP-001, AP-004
        ValReport/KnowledgeEntry
```
AP-101 gates all of Phase 1. After AP-101, AP-102/104/106/107/108/109/110/111/
112 fan out in parallel; AP-103 ← AP-102; AP-105 ← AP-103.

### Phase 2 (substrate)
```
AP-201  Event bus + store            ← AP-112, AP-001
AP-202  Idempotency/correlation      ← AP-201
AP-203  State engine + persistence   ← AP-112, AP-201, AP-202, AP-001
AP-204  Checkpoint store + restore   ← AP-111, AP-112, AP-203, AP-001
AP-205  Policy engine + registry     ← AP-112, AP-004, AP-201
AP-206  Artifact store               ← AP-111, AP-201
AP-207  Harness SDK + registry       ← AP-109, AP-108, AP-002, AP-201
```
AP-201 gates the substrate. AP-205/206/207 can proceed in parallel once their
object schemas + AP-201 exist.

### Phase 3 (understanding pipeline)
```
AP-301  Intent Resolution            ← AP-102, AP-205
AP-302  Context Harnesses            ← AP-207
AP-303  Context Engineering          ← AP-103, AP-301, AP-302
AP-304  Capability Resolution        ← AP-108, AP-109, AP-207
AP-305  Skill selection/composition  ← AP-107, AP-304
AP-306  Planning Engine              ← AP-104, AP-105, AP-303
AP-307  Execution Graph Builder      ← AP-104, AP-306
AP-308  Execution Strategy Generator ← AP-106, AP-306, AP-304
AP-309  Work Packaging               ← AP-105, AP-303, AP-305, AP-307
```
Critical sub-path: AP-301 → AP-303 → AP-306 → AP-307 → AP-309.

### Phase 4 (execution coordination)
```
AP-401  Orchestration                ← AP-307, AP-308, AP-203, AP-201, AP-205
AP-402  Resource alloc/scheduling    ← AP-109, AP-401
AP-403  Runtime adapter SDK + first  ← AP-207, AP-109
AP-404  More runtime adapters        ← AP-403
AP-405  Execution layer              ← AP-110, AP-403, AP-401
AP-406  Governance gate              ← AP-205, AP-401, AP-004
```
AP-401 gates Phase 4. AP-403 can start in parallel with AP-401 (both ← AP-207).

### Phase 5 (close the loop)
```
AP-501  Supervision                  ← AP-110, AP-201, AP-401
AP-502  Validation                   ← AP-110, AP-112, AP-205, AP-405
AP-503  Recovery                     ← AP-204, AP-501, AP-401, AP-106
```
Order within phase: AP-501 → AP-503; AP-502 parallel to AP-501.

### Phase 6 (learn + mature)
```
AP-601  Reflection                   ← AP-502, AP-111, AP-201
AP-602  Knowledge store + ingestion  ← AP-601, AP-206, AP-112
AP-603  Knowledge retrieval/feedback ← AP-602, AP-303, AP-306
AP-604  Operational maturity         ← AP-201, AP-203, AP-406, AP-501
```
Linear core: AP-601 → AP-602 → AP-603. AP-604 parallelizable late.

---

## Cross-Phase Dependency Highlights

- **AP-001 (persistence)** is the deepest root: AP-101, AP-112, AP-201, AP-203,
  AP-204 all trace back to it. It is the single highest-leverage decision.
- **AP-002 (registry unification)** roots AP-108, AP-109, AP-207, AP-304.
- **AP-003 (object reconciliation)** roots the whole Phase-1 schema set.
- **AP-207 (Harness SDK)** is the integration root for AP-302 (context), AP-403
  (runtime), and later Validation/Communication harnesses.
- **AP-401 (Orchestration)** is the execution-time hub: Supervision (501),
  Recovery (503), Governance (406), and Resources (402) all attach to it.

---

## Cycle Check

A static reading of the AP graph yields no cycles: every edge points to a
lower- or same-phase AP completed earlier. The architectural feedback edges
(Supervision→Orchestration, Recovery→Orchestration, Knowledge→Planning) are
**runtime data flows**, not build-time dependencies, and therefore introduce no
implementation cycle. This property must be preserved: if a future AP needs a
higher-phase AP to be *built* first, that is a design smell to resolve, not a
dependency to add.
