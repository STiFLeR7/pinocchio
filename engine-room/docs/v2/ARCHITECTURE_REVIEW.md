# Nexus v2 — Architecture Review

Status: Phase 0 Architecture Review Board (ARB) record
Date: 2026-06-26
Scope: Reviews the complete `docs/v2/` architecture and `blueprint/v2/`
implementation plan, records the Phase-0 ratifications (`adr/ADR-001..004`), the
contract freeze (`contracts/`), and the architectural invariants
(`docs/v2/99_ARCHITECTURAL_INVARIANTS.md`), and issues an implementation-
readiness verdict.

---

## 1. Executive Verdict

**Nexus v2 is cleared to begin implementation (Phase 0 → Phase 1).**

The architecture is structurally complete and internally coherent. The four
foundational decisions that previously blocked implementation are now ratified,
the canonical object contracts are frozen, and the architectural guardrails are
explicit. **No Critical blockers remain.** The items that remain are either
mechanical (documentation hygiene) or intentionally deferred (implementation-
level choices that the plan correctly defers to Phase 1/2).

**Overall implementation-readiness score: 8.6 / 10** — "ready to build the
foundation; redefine nothing core during development."

---

## 2. What This Review Ratified

| Decision | Record | Resolves |
|----------|--------|----------|
| Event-sourced persistence; log authoritative, state/checkpoints derived | `adr/ADR-001` | G1, G5, G10 |
| Four registries; Runtime⊂Harness; Resource = allocation projection | `adr/ADR-002` | G2 (+G10) |
| Canonical object model (one WP schema, graph sibling-of-Plan, Observation→Supervision, Intent rename, enum/Artifact fixes) | `adr/ADR-003` | G3, G4, G5, G6, G7, G9, G11 |
| Data-driven Policy, one approval taxonomy, determinism boundaries | `adr/ADR-004` | G8, G12, G13, G14 |
| 17 frozen logical contracts | `contracts/` | INV-07 across all objects |
| 39 architectural invariants | `docs/v2/99_ARCHITECTURAL_INVARIANTS.md` | permanent guardrails |

Of the 15 architecture gaps in `blueprint/v2/08_ARCHITECTURE_GAPS.md`, **14 are
now resolved by decision**; the sole remainder (**G15, documentation hygiene**)
is mechanical and owned by AP-007.

---

## 3. Architectural Strengths

1. **A genuinely coherent spine.** The 13-stage pipeline has clean,
   non-overlapping responsibilities and a strict one-way dependency flow. Every
   layer's "never" list partitions responsibility cleanly. This is the
   architecture's strongest property and it survived adversarial review.
2. **Evidence over confidence.** Completion is determined by independently
   verifiable Evidence, never runtime self-report (INV-20). This single decision
   makes the platform trustworthy across unreliable/non-deterministic runtimes.
3. **Runtime independence via the Harness.** One integration boundary for all
   external systems (Runtime/Context/Validation/Communication/…) means execution
   technology can churn without disturbing operational intelligence.
4. **Recover, don't restart.** Checkpoint + event-replay recovery preserves
   context, progress, and validated evidence — a strong operational-maturity
   stance most agent frameworks lack.
5. **Governed autonomy.** Deterministic, data-driven, fail-closed policy with an
   immutable audit (the event log itself) keeps human authority final without
   making execution synchronous.
6. **One source of truth (post-ADR-001).** Collapsing three candidate stores
   into an authoritative event log with derived projections removes the deepest
   correctness risk in the original architecture.
7. **Self-improvement is architected, not bolted on.** Validation → Reflection →
   Knowledge → Planning closes a learning loop with strict evidence gating.

---

## 4. Architectural Weaknesses (residual, post-ratification)

1. **Cognition is non-deterministic; the platform brackets it but cannot remove
   it.** Intent Resolution, LLM execution, and human/LLM validation remain
   non-deterministic. ADR-004 makes this honest (determinism of the *spine*, not
   of *models*; capture-as-data on replay), but operational variance is inherent.
   *Residual risk, not a defect.*
2. **Context Engineering is a large, under-specified surface.** 10+ external
   source types with no per-connector contracts and no first-class authorization
   model. The Harness boundary (Context Harnesses) contains this, but the
   security/permission model for external data is still a Phase-3 design debt.
3. **Embedded Context Package in every Work Package** risks transport/memory
   bloat at scale. ADR-003 permits Context-by-reference; this must be exercised,
   not just allowed.
4. **The Execution Graph is a single source of operational topology.** Powerful,
   but a correctness-critical structure; its projection/consistency (now under
   ADR-001) must be airtight.
5. **Estimation has no methodology.** Planning's complexity/cost/duration
   estimates start heuristic; strategy selection depends on them. Sanctioned
   debt, but watch it.
6. **Non-rollbackable side effects** (sent email, external mutations) have no
   universal recovery. Recovery's domain-specific rollback is correct but leaves
   a real operational hazard for integration actions.

None of these justify changing the v2 intent. All are tracked in
`blueprint/v2/05_RISKS.md` and `06_TECHNICAL_DEBT.md`.

---

## 5. Object Relationship Review (audit result)

Audited ownership, lifecycle, dependency direction, duplication, and hidden
coupling across all objects. Findings and resolutions:

- **Duplication removed:** Work Package (was 3 definitions → 1, ADR-003);
  Dependency Graph (eliminated; dependencies are graph edges); Runtime Registry
  (folded into Harness Registry, ADR-002).
- **Ownership fixed:** Observation → Supervision only (Execution emits Events);
  Evidence → Validation (Execution emits Candidates); Goal → Intent Resolution.
- **Containment fixed:** Execution Graph is a sibling artifact *referenced by*
  the Plan, not nested — decoupling two lifecycles.
- **Hidden coupling cut:** Planning no longer depends on Reflection (only on
  persisted Knowledge, INV-26); state no longer has three stores (one log,
  derived projections).
- **Simplification recommended and adopted:** Resource registry duties → Harness
  Registry + allocation projection; State/Checkpoint demoted to derived.

The frozen `contracts/` set is the materialization of this audit. The relationship
lineage `Goal → Context Package → Plan → Work Package → Execution Graph →
Execution Session → Evidence → Reflection → Knowledge` is now single-owner at
every hop.

---

## 6. Unresolved Questions (honest open list)

These are **intentionally open** (deferred by the architecture), not blockers.
Full catalog: `blueprint/v2/07_UNKNOWNS.md`. The critical-path-blocking unknown
(persistence model) is now **closed** by ADR-001. Remaining notable opens:

- **Serialization/wire format** for objects — decided in AP-101 (early Phase 1).
- **Message bus / event store technology** — Phase 2 (AP-201), compatible with
  ADR-001's "ordered, durable, append-only log per operation."
- **Storage backends** for artifacts/checkpoints/knowledge — Phase 2.
- **Algorithms** (context discovery/sufficiency, planning decomposition &
  estimation, capability resolution ranking, knowledge retrieval, supervision
  health thresholds, retry/backoff params) — start heuristic; refine with data.
- **External-source authorization model** — Phase 3 design item.
- **Capability/runtime trust & verification** (self-reported today) — future.

None require resolution before Phase 1 begins.

---

## 7. Implementation Blockers, Classified

**Critical (must resolve before Phase 1 schema work):**
- *None.* The four ADRs are ratified and contracts are frozen. This is the exit
  condition for "architecture blocks implementation."

**Important (resolve within Phase 0 / early Phase 1):**
- ✅ **AP-007 documentation hygiene** — *completed in the Phase 0 reconciliation
  pass:* `docs/v2/README.md` index corrected (lists 00–26 + 99 + REVIEW +
  MIGRATION + CONSISTENCY), `13_EXECUTION_MODEL.md` renamed to
  `13_EXECUTION_STRATEGY.md`, terminology reconciled. See `CONSISTENCY_REPORT.md`.
- ✅ **Object Model addendum** — *completed:* `02_OBJECT_MODEL.md` reconciled to
  Intent Resolution, given a contract-mapped ownership table, and banner-linked to
  ADR-003 and `contracts/`.
- ✅ **Consolidated v1 → v2 migration plan** — *completed:* `MIGRATION_FROM_V1.md`
  consolidates the conceptual mapping (outbox → log; runtime registry → Harness;
  `_ACTION_POLICY` → Policy set).
- **Serialization-format decision (AP-101)** — remains the first task of Phase 1.

**Nice to have:**
- Promote a standalone `contracts/validation_report.md` if Phase 1 finds it
  warranted (currently modeled via Work Package/Observation relationships).
- Predicate-vocabulary growth plan for the Policy condition language.
- Context-by-reference exercised early to validate the anti-bloat path.

---

## 8. Recommendations

1. **Execute Phase 0's remaining mechanical AP-007 work next**, then start Phase 1
   AP-101 (serialization) immediately — it gates all schema work. *Why:* removes
   the only Important documentation debt and unblocks the widest fan-out.
2. **Treat the `contracts/` directory as frozen.** Changes require an ADR. *Why:*
   contract drift is the platform's highest historical risk (INV-07); freezing is
   the mitigation.
3. **Stand up the contract-test harness (AP-006) before writing schemas.** *Why:*
   it is the enforcement mechanism for INV-07..INV-12 and every seam.
4. **Build the event store + projection engine + idempotency first in Phase 2**
   (AP-201/203/202), then checkpoint/policy/artifact/harness. *Why:* ADR-001 makes
   these the spine everything else rides on.
5. **Invest in the Harness SDK (AP-207) early and well.** *Why:* Context, Runtime,
   Validation, and Communication harnesses all inherit it — highest reuse leverage.
6. **Author the consolidated migration plan** before touching v1 services, to
   preserve v1 operational guarantees (governance fail-closed, approval gates).
7. **Write a one-page `risk_level` computation note** before Phase 4 governance —
   it is an input to every approval-tier decision and is currently undefined.

---

## 9. Implementation Readiness Scorecard

| Dimension | Score /10 | Notes |
|-----------|-----------|-------|
| Architectural boundaries | 9.5 | Clean, one-way, single-responsibility; invariants published. |
| Object contracts | 9.0 | 17 frozen; one schema per object; one Important addendum pending (`02`). |
| Foundational decisions | 9.5 | ADR-001..004 ratified with alternatives/trade-offs. |
| Registry reconciliation | 9.0 | Four registries, single field ownership; migration noted. |
| Persistence strategy | 9.0 | Event-sourced, projections, checkpoints derived; tech TBD (Phase 2, expected). |
| Invariants / guardrails | 9.5 | 39 enforceable invariants mapped to tests. |
| Testing & validation plan | 8.5 | Phase gates + per-subsystem strategy exist; harness to be built (AP-006). |
| Documentation hygiene | 6.5 | AP-007 index/rename/glossary + `02` addendum outstanding. |
| Migration (v1 → v2) | 7.0 | Per-ADR sections exist; consolidated plan pending. |
| Unknowns management | 8.5 | Critical-path unknown closed; rest deferred with owners. |
| **Overall** | **8.6** | **Ready to implement; nothing core needs redefinition during development.** |

---

## 10. Required Phase 0 Decisions — Status

| Decision | Status |
|----------|--------|
| Persistence & State Model | ✅ Ratified — ADR-001 |
| Registry Architecture | ✅ Ratified — ADR-002 |
| Canonical Object Model | ✅ Ratified — ADR-003 |
| Policy Engine & Governance | ✅ Ratified — ADR-004 |
| Canonical contracts frozen | ✅ `contracts/` (17 + README) |
| Architectural invariants | ✅ `docs/v2/99_ARCHITECTURAL_INVARIANTS.md` (39) |
| Documentation hygiene (index/rename/glossary) | ✅ Done — Phase 0 reconciliation pass |
| Object Model addendum (`02`) | ✅ Done — reconciled + contract-mapped |
| Consolidated v1→v2 migration plan | ✅ Done — `MIGRATION_FROM_V1.md` |
| Serialization format | ⏳ Deferred to AP-101 (Phase 1, expected) |

---

## 11. ARB Decision

**APPROVED to proceed to implementation.** Begin with the remaining AP-007
documentation hygiene and the Object Model addendum (Important), then Phase 1
starting at AP-101 under the frozen `contracts/`. Re-convene the ARB only on a
proposed change to a ratified ADR or a frozen contract, or at each phase
validation gate per `blueprint/v2/10_VALIDATION_STRATEGY.md`.

Implementation may now begin with minimal architectural ambiguity and without
redefining core concepts during development — the success criterion for this
review.
