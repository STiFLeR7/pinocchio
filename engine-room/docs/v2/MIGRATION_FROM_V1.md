# Nexus — Conceptual Migration from v1 to v2

Status: Phase 0 baseline
Scope: **Conceptual** evolution of the architecture. This document explains how
v1 concepts map to v2 concepts and why. It does **not** describe code, data, or
deployment migration — only how to think about the change.

---

## 1. The Shift in One Sentence

Nexus v1 is an **AI Orchestration Control Plane** that reliably *executes*
governed work. Nexus v2 is an **Operational Intelligence Platform** that
*understands* work before executing it — execution becomes one replaceable
capability among many, and operational intelligence (context, planning,
supervision, validation, learning) becomes the durable core.

v1 answered "how do we run this task safely?" v2 answers "what work actually
needs to happen, and how do we know it succeeded?"

---

## 2. Renamed Concepts

| v1 concept | v2 concept | Why |
|------------|-----------|-----|
| Executive Intelligence *(early v2 draft term)* | **Intent Resolution** | The layer's job is to resolve operator requests into normalized Goals; the precise name replaces the vague one (ADR-003). |
| Chat planner / command interpreter (Dex pipeline) | **Intent Resolution** → **Planning** | v1 conflated "understand the request" with "decide the actions." v2 separates intent normalization (Goal) from work decomposition (Plan). |
| Task | **Work Package** | A Work Package is the runtime-independent, evidence-bearing unit of work — a richer, governed successor to the v1 task. |
| Runtime adapter / execution wrapper | **Harness (Runtime category)** | All external systems integrate through one common boundary; runtimes are one Harness category (ADR-002). |
| Runtime Registry | **Harness Registry** | The single registry of integration boundaries and the sole source of provider availability/health (ADR-002). |
| `_ACTION_POLICY` governance flags | **Policy** objects + **Policy Engine** | Hardcoded action flags become declarative, versioned, deterministically-evaluated policies (ADR-004). |
| Transactional outbox (`SystemOutboxRecord`) | **Event Log** (authoritative) | v1's outbox is the seam: in v2 the append-only event log becomes the single source of operational truth (ADR-001). |
| Channel router / communication / Discord / email | **Communication Harness** | Communication channels become Harnesses under the common contract. |
| Research / source fetchers | **Context Harness** | Context sources become read-oriented Harnesses feeding Context Engineering. |
| Memory (single persistent store) | **Reflection → Knowledge** pipeline | v1 *recorded* information; v2 *interprets* validated outcomes (Reflection) and *persists understanding* (Knowledge). "Memory records; Knowledge explains." |

---

## 3. Removed / Subsumed Concepts

| v1 concept | Status in v2 | Rationale |
|------------|--------------|-----------|
| Runtime Registry as a peer registry | **Subsumed** by the Harness Registry | Eliminates duplicate provider/health/availability ownership (ADR-002). |
| Memory as a single undifferentiated store | **Split** into Reflection (interpretation) + Knowledge (validated, evidence-backed graph) | Recording ≠ understanding; only validated learning should influence future planning. |
| Self-reported task completion | **Removed** | Completion is determined by independent Evidence, never runtime self-report (INV-20). |
| Ad-hoc per-runtime execution wrappers | **Replaced** by one Harness contract | Provider differences are isolated at a single boundary (INV-34). |
| Separate "Dependency Graph" output | **Removed** | Dependencies are edges in the Execution Graph (ADR-003). |
| State stored as authoritative rows | **Demoted** to a projection of the event log | One source of truth; replay and recovery require a derived read model (ADR-001). |

---

## 4. Newly Introduced Concepts

These have **no v1 equivalent** — they are the substance of the v2 thesis:

- **Context Engineering / Context Package** — assemble and validate operational
  context before planning. v1 had no context-assembly layer.
- **Planning Engine / Plan / Execution Graph** — decompose a Goal into a
  validated, acyclic topology of Work Packages. v1 executed largely reactively.
- **Execution Strategy** — declarative, runtime-agnostic coordination behavior
  (sequencing, approval, retry, timeout, validation, recovery, checkpoint).
- **Skills & Capability Model** — reusable, runtime-independent procedures and
  the abstract capabilities they require (capability-first, not model-first).
- **Supervision** (distinct layer) — derive operational health from event
  streams and *recommend* intervention (Orchestration acts).
- **Validation** (distinct layer) — evidence-based completion, independent of
  execution.
- **Recovery Engine** — classify failure, restore from checkpoint, resume
  (recover, don't restart).
- **State / Event / Checkpoint substrate** — event-sourced operational truth
  with derived state projections and reference-based checkpoints.
- **Architectural invariants** — 39 permanent guardrails
  (`99_ARCHITECTURAL_INVARIANTS.md`).

---

## 5. Architectural Rationale (why the evolution)

1. **Execution is commoditized; understanding is not.** v2 invests where the
   durable value is — context, planning, supervision, learning.
2. **Capabilities over models.** Runtimes churn; capabilities persist. The
   Harness + Capability model lets execution technology change without
   disturbing operational intelligence.
3. **Evidence over confidence.** Trustworthy outcomes require independent
   verification, not runtime self-report.
4. **One source of truth.** An authoritative event log makes audit, replay,
   recovery, and knowledge native rather than bolted on.
5. **Recover, don't restart.** Checkpoints + replay preserve progress, context,
   and validated evidence across failures.
6. **Deterministic governance over cognitive autonomy.** Governance and
   coordination are deterministic and auditable; model cognition is bracketed
   and captured-as-data (ADR-004).

---

## 6. Conceptual Migration Mapping (at a glance)

```
v1                                  v2
──────────────────────────────     ─────────────────────────────────────────
Operator request / chat        →    Intent Resolution → Goal
(implicit context)             →    Context Engineering → Context Package
(reactive task creation)       →    Planning → Plan + Execution Graph + Strategy
Task                           →    Work Package
Runtime Registry + adapters    →    Harness Registry + Harnesses (Runtime)
_ACTION_POLICY flags           →    Policy Engine + Policy (declarative)
Approval gate (Discord)        →    Governance approval workflow
                                    (Automatic/HumanReview/MultiStage/Deferred)
Execute task                   →    Orchestration → Execution (evidence candidates)
(self-reported done)           →    Supervision (health) → Validation (evidence)
(no recovery model)            →    Recovery (classify → restore → resume)
Outbox (SystemOutboxRecord)    →    Event Log (authoritative)
Memory                         →    Reflection → Knowledge (validated graph)
Briefings / operational intel  →    Knowledge-driven planning + Supervision health
```

---

## 7. Compatibility Notes (preserving v1 guarantees)

The v2 evolution **preserves** v1's hard operational guarantees:

- **Fail-closed governance.** v1's "A-001 must fail closed" becomes the v2
  **Default Policy** (deny-by-default for governed actions, ADR-004 / INV-30).
- **Human approval is final.** v1 approval gates become the Governance approval
  workflow; autonomy never replaces accountability.
- **At-least-once + idempotent delivery.** v1's outbox semantics become the
  Event delivery contract (at-least-once + platform idempotency, ADR-001 /
  INV-16).
- **Deterministic server-side governance.** v1 stamps governance flags
  server-side (never from the chat LLM); v2 keeps cognition out of governance —
  only the Policy Engine decides (INV-28), consistent with the determinism
  boundary.

These are **conceptual** compatibility statements. The path from v1 structures
to v2 structures (outbox → log, registry → harness, action table → policies) is
designed to be incremental, and each ratified ADR records its own migration
considerations. No conceptual boundary in v2 contradicts a v1 guarantee; v2
generalizes them.

---

## 8. What a v1 Reader Should Internalize

- A "task" is now a **Work Package** — and it never completes on the runtime's
  say-so.
- A "runtime" is now one **Harness** — and the platform reasons about its
  **capabilities**, not its API.
- "Memory" is now two things — **Reflection** (what we learned) and
  **Knowledge** (validated understanding that improves future planning).
- "Governance flags" are now **Policies** evaluated by one deterministic engine.
- The system's truth lives in **one event log**; everything else is a view of it.
