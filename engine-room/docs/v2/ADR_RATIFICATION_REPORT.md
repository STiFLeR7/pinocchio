# ADR Ratification Report — P0 Decision Closure

- **Date:** 2026-07-13
- **Scope:** ratification of ADR-007 (Persistence Authority) and ADR-008 (Shadow Decision Migration) from the completed P0 spikes.
- **Rule observed:** no implementation, no production code, no commits, no redesign. These ADRs ratify decisions already evidenced by the spikes; they introduce no new architecture.

---

## 1. What Changed

- **Two ADRs filed** in the v2 constitutional `adr/` series: `adr/ADR-007-persistence-authority.md` and `adr/ADR-008-shadow-migration.md`. The series previously stopped at ADR-004.
- **The numbering collision is resolved by series.** `blueprint/DECISIONS/` contains legacy v1-era ADRs including `ADR-007-email-provider.md` and `ADR-008-discord-authorization.md`; the new ADRs live in the separate v2 `adr/` series, and each records the distinction in its header. "ADR-007" and "ADR-008" hereafter denote the v2 decisions.
- **Two logical decisions became authoritative documents:** the persistence-authority decision (readiness C1 / H1 / H2) and the shadow-migration decision (readiness C2 / H3), both front-loaded per C6.
- **No source, contract, or invariant was modified.** ADR-007 adds *durability* to the existing event-sourcing model without schema change; ADR-008 adds a *migration mechanism* without touching decision ownership.

## 2. What Was Ratified

**ADR-007 — Persistence Authority.** The append-only Event Log remains the single authoritative source of truth (reaffirming ADR-001); durability is added **behind the existing synchronous protocols** using a synchronous `sqlite3` driver, with the `VersionedSerializer` as the concrete format and store-assigned positions persisted. **v2 stays fully synchronous — no async bridge.** v1's mutable tables are demoted to projections via the transactional-outbox seam ("the outbox becomes the log"). Rejected: v1-CRUD authority (ADR-001's already-rejected Alternative A; INV-13 blocker), the async→sync bridge (unnecessary, deadlock-prone), making v2 async (blast radius over 0 existing `async def`), and projection-less event sourcing (ADR-001 §4.B).

**ADR-008 — Shadow Decision Migration.** Decisions migrate **one constitutional owner at a time** via **Recorded Shadow Adjudication**: `DecisionRecord` / `ShadowDecision` / `DecisionDiff` are recorded as events in the durable log; the v2 owner is proven equivalent in shadow — **side-effect-free (INV-29)** — before it becomes authoritative behind a **per-owner feature flag**; **comparison is by determinism class** (exact for rules; equivalence-band/semantic/human for the LLM decisions); and the **Policy Engine migrates first** (the universal governance leaf). Conflated v1 decisions are decomposed via an explicit map. Rollback is a per-owner flag flip. Rejected: big-bang cutover, flag-only rollout, exact-match-only shadow, forked parallel product, and per-decision migration ignoring the Policy leaf.

**Consistency check (performed before writing):** every statement in both ADRs was verified against the Constitution (decision ownership, Policy-leaf rule, determinism model), the existing ADRs (ADR-001 event authority and rejected alternatives; ADR-004 Policy-vs-Governance boundary and determinism boundaries), the frozen contracts (`event.md`, `checkpoint.md`, `policy.md` unchanged), and the invariants (INV-01/07/13/14/16/17/22/23/28/29/30/37/39). No statement contradicts them; no new architectural claim was introduced. Unsupported phrasing from the Blueprint ("share truth / no behavior change") was explicitly superseded rather than repeated, because the Readiness Review and INV-13 contradict it.

## 3. Remaining Unresolved Architectural Work

Ratifying these two ADRs closes the persistence and migration-mechanism decisions. It does **not** close all of P0. Outstanding:

- **C3 — Estimation.** The Estimation model and the freeze of the `estimation` / `engineering_strategy` contract are not yet decided (Engineering Program P0.E3 / P8).
- **C4 — Operations.** The Operations plane design doc is not yet written (P0.E4 / P9).
- **C5 — Contract freezes.** `repository_understanding`, `interaction`, and `environment` contracts are not yet frozen (P0.E5 / P4–P6).
- **ADR-009 / ADR-010** (per the Engineering Program): runtime-registry unification and the correlation-event gateway / INV-39 transport freeze remain to be written. *(Update, RC1, 2026-07-21: `adr/ADR-009-runtime-selection-ownership.md` has since been filed — under a narrower, related topic, "Runtime Selection Ownership" resolving an INV-37 wording contradiction, rather than the broader "runtime-registry unification" anticipated here. Status: **Proposed**, not yet ratified. ADR-010 remains unwritten.)*
- **Confirming spikes (not decisions).** ADR-007 and ADR-008 ratify *direction*; their Validation sections list executable confirmations that are the **entry gate for implementation** (durable-store parity/replay/atomicity for ADR-007; determinism-class comparison, side-effect isolation, and per-owner rollback for ADR-008). These are scheduled P1/P3 work, not re-opened architecture — exactly as ADR-001 was ratified ahead of its Phase-2 validation tests.
- **Greenfield owners.** Risk/autonomy classification and execution retry have no v1 counterpart; their behavioral acceptance gates are defined by ADR-008 but the subsystems are unbuilt.

## 4. Is P0 Decision Closure Complete?

**Partially — the two hardest, most blocking decisions are closed; three conditions remain open.**

| Readiness condition | Status |
|---|---|
| **C1** — rewrite ADR-007 (sync/async + event-log authority) | **Closed** — `adr/ADR-007-persistence-authority.md` |
| **C2** — complete ADR-008 (flag/shadow mechanism) | **Closed** — `adr/ADR-008-shadow-migration.md` |
| **C6** — move Policy Engine + ADR-007/008 to the front | **Substantially closed** — both front-loaded decisions ratified; Policy-first order is now authoritative in ADR-008 |
| **C3** — Estimation model + freeze contract | **Open** |
| **C4** — Operations design doc | **Open** |
| **C5** — freeze repository_understanding / interaction / environment | **Open** |

**Conclusion:** P0 is **not fully complete**, but its critical path is unblocked. C1/C2 were the irreversible-risk decisions (INV-13 persistence authority; the migration mechanism with the INV-39 gap); both are now ratified, front-loaded, and mutually consistent (ADR-008 depends on ADR-007). The remaining conditions (C3/C4/C5) are contract-freeze and design work that gate their respective subsystems (Estimation, Operations, and the grounding/interaction/actuation family) but do not block P1 (Durable Foundation) or P2 (Policy Engine). Recommended next action per the Engineering Program: begin P1 against ADR-007 while closing C3/C4/C5 in parallel.

---

## 5. ADR-005/006 Gap and the ADR-010 Numbering Collision (added by Phase 5's documentation audit)

This report's job is tracking every ADR's status; two gaps in that tracking were found and are recorded
here rather than left silent (full investigation: `docs/DOCUMENTATION_PHASE5_REPORT.md` §2).

- **ADR-005 and ADR-006 were never filed.** Both are referenced prospectively across
  `ARCHITECTURE_CONSTITUTION.md`, `CONSTITUTIONAL_MIGRATION_BLUEPRINT.md`,
  `IMPLEMENTATION_READINESS_REVIEW.md`, and `CONSTITUTIONAL_ENGINEERING_PROGRAM.md` — always as a decision
  "to ratify," never as a past-tense claim of acceptance (the one table cell reading "Accepted in P0" is
  under a column literally headed "Status target"). Git history has no trace of either number ever
  existing as a file. Both decisions' substance shipped anyway: `nexus_engineering` (ADR-005's Engineering
  Intelligence split) and `nexus_policy`/`nexus_repository`/`nexus_human_interaction`/`nexus_operations`
  (ADR-006's subsystem-naming, one of its two conflicting drafted definitions) are real, tested packages.
  `CONSTITUTIONAL_ENGINEERING_PROGRAM.md`'s *other* definition of ADR-006 ("Program Sequencing") was
  ratified, but its decision was absorbed into ADR-008 rather than filed under its own number — see §2
  above, "Policy-first order is now authoritative in ADR-008." No ADR-005/006 file has ever existed to be
  lost, and none is fabricated here.
- **ADR-010 is a numbering collision this report previously didn't flag.** v2's own planned ADR-010
  (correlation-event gateway / INV-39 transport freeze) remains unwritten, as already noted above. Separately,
  and unrelated to it, `blueprint/DECISIONS/ADR-010-execution-timeouts.md` is v1's real, ratified,
  independently-numbered ADR-010 — actively cited in shipped v1 code (`nexus/execution/runners/*.py`,
  `docs/v1/ORCHESTRATION.md` §6.1). The two must not be conflated; v1's ADR-010 is not a gap of any kind.

---

### References
- `adr/ADR-007-persistence-authority.md`, `adr/ADR-008-shadow-migration.md`
- `docs/v2/P0_ADR007_PERSISTENCE_SPIKE.md`, `docs/v2/P0_ADR008_SHADOW_MIGRATION_SPIKE.md`
- `adr/ADR-001.md`, `adr/ADR-004.md`
- `docs/v2/IMPLEMENTATION_READINESS_REVIEW.md` (C1–C6, H1–H3), `docs/v2/CONSTITUTIONAL_ENGINEERING_PROGRAM.md` (P0–P3)
