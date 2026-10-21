# ADR-008 — Shadow Decision Migration

- **Status:** Accepted (Phase 0, ratified)
- **Date:** 2026-07-13
- **Deciders:** Architecture Review Board
- **Relates:** ratifies `docs/v2/P0_ADR008_SHADOW_MIGRATION_SPIKE.md`; **depends on ADR-007** (the durable Event Log is the recording medium); depends on ADR-001 (events authoritative; determinism via captured data) and ADR-004 (Policy Engine evaluates; determinism boundaries). Closes readiness condition **C2** and hidden decision **H3** (flag/shadow mechanism; INV-39 gap).
- **Affected work:** Engineering Program **P3** (Strangler Integration Substrate) and every per-owner migration (**P2, P4–P10**).
- **Numbering note:** filed in the v2 constitutional `adr/` series at 008, distinct from `blueprint/DECISIONS/ADR-008-discord-authorization.md` (legacy series). "ADR-008" hereafter denotes this decision.

---

## 1. Context

The constitutional goal is to replace v1's decisions **one owner at a time while the product remains continuously operational**. The Constitution fixes exactly one owner per decision (Canonical Decision Ownership; INV-02) and establishes that every governed decision depends on the Policy Engine, which must therefore be a leaf depending only on the Event Log and policy data.

The migration spike verified the ground it must cross: v1 makes ~44 production decisions, most deterministic (rule/config/state-machine), a minority non-deterministic (four LLM decisions — intent classification, agent plan, agent tool-loop, research importance score — plus four environmentally non-deterministic ones: provider fallback, live-git reads, backoff jitter, lock races). The migration substrate the Blueprint presupposes — feature flags, decision-provenance logging, result diffing, shadow execution, canary routing, decision replay, decision rollback — **does not exist in source**. Reusable assets: v2's correlation+causation+sequence spine, v2 state-replay, v1's transactional outbox pattern, v1's correlation-indexed audit ledger, and the pydantic/policy config store as a flag host.

## 2. Problem Statement

Three source-level facts make a naive migration unsafe:

- **v1 conflates constitutional owners.** The primary decision (`nexus/communication/chat/planner.py`) fuses Intent (→ Intent Resolution), kind-of-work (→ Engineering Intelligence), and approval-required (→ Policy Engine) in one LLM call plus a config table; policy is additionally spread across the validator, the 11-check governance gate, and the policy store. A 1:1 "port planner.py to EI" is impossible.
- **Exact-match comparison breaks on non-deterministic decisions.** v1's biggest decision is an LLM classification; two engines legitimately differ token-by-token while being equivalent. Naive "log the difference" would emit a false-mismatch storm and could trigger spurious rollbacks.
- **Nothing records or isolates decisions today.** There is no place that records "given inputs X I chose Y" for comparison, and no guarantee a parallel computation performs no side effect.

Two "migrations" have **no v1 counterpart to replace**: risk/autonomy classification (the Discord "Risk Level" is a hardcoded `"LOW"`) and execution retry (failed executions go straight to FAILED; only *notifications* retry). These are greenfield builds with a constitutional owner.

## 3. Decision

**Decisions migrate one constitutional owner at a time via Recorded Shadow Adjudication: each v1 decision, its v2 shadow, and their classified diff are recorded as events in the durable Event Log (ADR-007); the v2 owner is proven equivalent in shadow — side-effect-free — before it becomes authoritative behind a per-owner feature flag; comparison is performed by determinism class; and the Policy Engine migrates first.**

### 3.1 Migrate authority per constitutional owner, decomposing conflated decisions

Migration is scoped to a single constitutional owner at a time (INV-02: one owner per decision). Where v1 conflates owners, an explicit **decomposition map** feeds the same recorded v1 inputs to each v2 owner's shadow (at minimum `planner.py` → {Intent Resolution, Engineering Intelligence, Policy Engine}; the four policy sites → the single Policy Engine). Migration relocates *and decomposes*; it never ports a conflated decision as one unit.

### 3.2 Recorded Shadow Adjudication (the five stages)

Per owner *O*: **Instrument** (v1 emits a `DecisionRecord` event at O's boundary — inputs, v1 output, decision identity, engine version, correlation) → **Shadow** (v2 *O* computes from the same recorded inputs, side-effect-free; emits a paired `ShadowDecision`; a comparator emits a classified `DecisionDiff`; v1 stays authoritative) → **Canary** (flag-gated cohort makes v2 authoritative while v1 reverse-shadows) → **Default** (v2 authoritative; v1 shadows as a safety net) → **Removal** (delete v1's site for O once the per-owner exit gate holds for a bake period). All three record types are **events in the durable Event Log** (INV-13/17), tied under one correlation stream (INV-39), which makes every diff replayable.

### 3.3 Comparison depends on determinism class

The comparator's verdict is a function of the decision's determinism class: **exact match** for deterministic rule/config decisions; **equivalence-band / semantic / human-adjudicated** for the non-deterministic decisions (per ADR-004's determinism boundaries — the platform guarantees determinism of coordination/governance, not of cognition). Applying exact-match to an LLM decision is a defect, not a mismatch.

### 3.4 The Policy Engine migrates first

Because every governed decision depends on the Policy Engine and it must be a leaf (Constitution: "a universal dependency must be a leaf"), **Policy is migrated before any owner it governs**. This aligns with readiness condition C6 and Engineering Program P2, and lets every later owner inherit governance for free. Thereafter migration follows the constitutional decision flow: Intent Resolution → Engineering Intelligence → Orchestration (runtime selection) → Recovery (retry) → Human Interaction (channel/approval surface) → Validation → the remainder.

### 3.5 Shadow is side-effect-free (mandatory)

A v2 shadow computation **performs no external effect** — no outbox write, no runner spawn, no actuation — consistent with INV-29 (Governance authorizes; it never executes). Any event emitted under a shadow's correlation id other than `ShadowDecision`/`DecisionDiff` is a bug. Side-effect isolation is what makes running two decision engines in production safe.

### 3.6 Rollback is per-owner

Each owner's authority is gated by a **runtime-mutable feature flag** (hosted in the pydantic settings or the versioned policy store). Rolling an owner back is a single flag write — atomic, no redeploy, **owner-scoped** (never a global revert), and evidence-preserving (the full decision/diff history remains in the log, INV-13/17). Because v1's site is retained until Removal, a rollback simply lets v1 recompute. Rollback of Policy is privileged and defaults-safe (a bad engine flips to v1's fail-closed defaults). Removal (deleting v1) is the only irreversible step, gated on a bake period and an atomic-revert deletion.

## 4. Alternatives Considered

- **Big-bang cutover.** *Rejected:* the product must remain continuously operational and every step reversible; a flag-day swap is neither.
- **Flag-only rollout (no shadow).** *Rejected:* provides no pre-cutover equivalence evidence — flipping a flag blind cannot show the v2 owner decides correctly.
- **Exact-match-only shadow.** *Rejected:* the four LLM decisions never match token-for-token; exact-match would produce a false-mismatch storm and erode trust in the harness.
- **Forked parallel v2 product.** *Rejected:* two live products diverge without bound; the INV-07 dual-representation debt becomes permanent rather than a closed, time-boxed exception.
- **Per-decision migration ignoring the Policy leaf.** *Rejected:* migrating a governed owner before Policy inverts the governance dependency; the leaf must move first.

## 5. Trade-offs

- **Gain:** the product stays live and releasable throughout; every cutover is evidence-backed and reversible on a flag; conflated ownership is corrected during migration; diffs are replayable, not anecdotal.
- **Cost:** the shadow/flag/comparison/decision-replay substrate must be built (it does not exist); a bounded period of dual decision representation per owner (INV-07 exception); non-deterministic owners need a defined equivalence band rather than a trivial equality.
- **Accepted because:** continuous operation with per-owner reversibility is the only safe way to replace a running product's decisions, and recording-as-events reuses the substrate ADR-007 already builds.

## 6. Consequences

- **P3 (Integration Substrate)** builds the feature-flag host, `DecisionRecord`/`ShadowDecision`/`DecisionDiff` event types and comparator, and the correlation gateway; **it does not proceed to Stage 1 for any owner until ADR-007's durable log exists.**
- Every per-owner migration (P2, P4–P10) follows the five stages; the durable log is the recording medium and rollback substrate.
- The two greenfield owners (risk/autonomy, execution-retry) are introduced against their documented v1 baseline (hardcoded LOW; no-retry) with a **behavioral acceptance gate**, not an equivalence gate.
- A decomposition map artifact is required before Stage 1 of any conflated owner.

## 7. Risks

- **R1 — owner-conflation leakage** (a diff attributed to the wrong owner). *Mitigation:* the decomposition map assigns every diff to exactly one owner; an unattributable diff is a map defect (INV-02).
- **R2 — false mismatch on LLM decisions.** *Mitigation:* determinism-class comparison; equivalence band per non-deterministic owner.
- **R3 — shadow causes a side effect.** *Mitigation:* side-effect isolation (INV-29); a guardrail asserts zero non-diff events under a shadow correlation id.
- **R4 — cohort instability** (a user flips buckets mid-session). *Mitigation:* pin the canary cohort by a stable key.
- **R5 — governance regression** if Policy migrates wrong. *Mitigation:* Policy is first and flag-gated to v1's fail-closed defaults; verdict parity proven in shadow (INV-28/30).
- **R6 — premature v1 deletion.** *Mitigation:* Removal gated on a bake period and grep-zero-references; atomic-revert deletion (INV-07 converge-then-delete).

## 8. Migration Impact

- **Order:** substrate (P3) → **Policy Engine first** (P2) → Intent Resolution → Engineering Intelligence → Orchestration (runtime) → Recovery (retry) → Human Interaction → Validation → periphery.
- **Per owner:** Instrument → Shadow → Canary → Default → Removal, each flag-gated and default-safe (v1 authoritative until proven).
- **Coexistence:** a declared, time-boxed INV-07 dual-representation window per owner, closed by converge-then-delete.
- **Greenfield owners:** introduced with a behavioral gate, not a comparison partner.

## 9. Validation

Ratifies the *strategy*; the entry gate for Stage 1 of any owner (P3) is:

- **Comparison proven on one deterministic and one non-deterministic owner:** exact-match works for a rule decision (v2 policy verdict vs v1 `policy_service`); an equivalence-band/semantic verdict works for an LLM decision (intent type), with no false-mismatch storm.
- **Side-effect isolation demonstrated:** a shadow run emits `DecisionDiff` events but **zero** outbox/runner events under its correlation id (INV-29 guardrail).
- **Per-owner rollback demonstrated:** flipping an owner's flag returns authority to v1 atomically, no redeploy, with full decision/diff history preserved (INV-13/17).
- **Order honored:** no governed owner defaults-on before the Policy Engine is authoritative.
- **Decomposition map present** for every conflated owner before its Stage 1.

## 10. Future Evolution

- Decision replay matures into a standing regression oracle: recorded inputs re-run against a new v2 revision detect behavioral drift before release.
- The comparator's equivalence bands become per-owner policy, tunable without code change.
- The correlation gateway generalizes from in-process to out-of-process transport (INV-39) without changing the recording contract.

## 11. References

- `docs/v2/P0_ADR008_SHADOW_MIGRATION_SPIKE.md` (the evidence this ADR ratifies)
- `adr/ADR-007-persistence-authority.md` (the durable recording medium — hard dependency)
- `adr/ADR-001.md` (events authoritative; determinism via captured data), `adr/ADR-004.md` (Policy evaluates; determinism boundaries; fail-closed default)
- `docs/v2/ARCHITECTURE_CONSTITUTION.md` (Canonical Decision Ownership; the Policy-leaf rule; decision/approval flows)
- `docs/v2/IMPLEMENTATION_READINESS_REVIEW.md` (C2, C6, H3), `docs/v2/CONSTITUTIONAL_ENGINEERING_PROGRAM.md` (P2, P3)
- Invariants: INV-02, INV-07, INV-13, INV-17, INV-22, INV-23, INV-28, INV-29, INV-30, INV-37, INV-39
- Source: `nexus/communication/chat/{planner,validator,service,executor}.py`, `nexus/execution/governance.py`, `nexus/memory/policy_service.py`, `nexus/gateway/communication_outbox.py`, `nexus_core/domain/event.py`
