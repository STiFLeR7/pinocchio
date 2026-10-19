# P0 Spike — ADR-008 Shadow Decision Migration

**Type:** Technical spike (evidence only — no production code, no commits)
**Purpose:** Determine how v2 decisions become authoritative **one owner at a time while the v1 product stays continuously operational**. This spike is about *decision migration*, not persistence (persistence is ADR-007, `docs/v2/P0_ADR007_PERSISTENCE_SPIKE.md`).
**Method:** Every claim is verified from source (file:line) or a ratified document, and labelled **[FACT]**, **[ASSUMPTION]**, or **[RECOMMENDATION]**. Prior conclusions were **not** trusted; two independent source sweeps (v1 decision surface; repo-wide migration-infra audit) plus a direct read of the Constitution's Canonical Decision Ownership table were performed.

> **Headline:** v1 makes **~44 production decisions**, but only a handful map to constitutional *reasoning* owners — most are deterministic rule/config. The migration substrate the Blueprint presupposes (flags, decision logging, diffing, shadow, canary, decision-replay, decision-rollback) **does not exist in source**; only a config host, an audit ledger, a transactional outbox, and v2's correlation+state-replay spine are reusable. The generic *Current→Shadow→Canary→Default→Removal* model is a **sound skeleton but insufficient as written** for three evidence-backed reasons (non-deterministic decisions can't be exact-matched; v1 *conflates* multiple constitutional owners in single decisions; shadowing must be recorded-as-events and side-effect-free). This spike recommends one enhanced strategy — **Recorded Shadow Adjudication per Constitutional Owner** — and sequences it by the constitutional rule that the **Policy Engine is the universal governance leaf** and therefore migrates first.

---

## 1. Executive Summary

**[FACT] The constitutional target is fixed.** Constitution *Canonical Decision Ownership* (`ARCHITECTURE_CONSTITUTION.md:307-329`) assigns exactly one owner per decision; Article III: *"One responsibility, one owner, one decision-point (INV-02)… Every decision in this document has exactly one owner"* (`:80-81`). The governing constraint on *order*: *"Every governed decision depends on the Policy Engine; therefore the Policy Engine may depend on nothing but the Event Log and policy data. A universal dependency must be a leaf"* (`:297-299`).

**[FACT] v1's decision surface is real and mostly deterministic.** 44 decision points enumerated from source. Only **four are non-deterministic (LLM-based)**: intent→ChatAction type (`communication/chat/planner.py:109-158`, temp 0.2 via `intelligence/openrouter.py:96`), the agent tool-loop next-action (`execution/runners/nexus_agent.py:288-333`), agent plan generation (`:181-213`), and research importance score (`intelligence/research.py:561-595`). Everything else is rule/config/state-machine and deterministic.

**[FACT] v1 conflates constitutional owners.** The single biggest v1 decision — `planner.py:109-158` — fuses three constitutional owners in one LLM call plus a config table: it picks the **intent/action** (→ Intent Resolution), implies the **kind of work** (→ Engineering Intelligence), and stamps **approval-required** via `_ACTION_POLICY` (`planner.py:63-70` → Policy Engine). Governance is likewise spread across four sites: the planner table, the validator (`chat/validator.py:39-56`), the 11-check governance gate (`execution/governance.py:60-653`), and the policy store (`memory/policy_service.py:54-95`). **Migration must decompose, not merely relocate.**

**[FACT] The migration substrate is essentially absent.** Repo-wide audit verdicts: feature flags **DO NOT EXIST** (`grep feature_flag` = 0 in source; only per-job `enabled` config in `config.py:109-160`); decision-provenance logging **DOES NOT EXIST** (policies are never even evaluated — `nexus_harness/policy_resolver.py:7` *"resolves… never evaluates… computes no decision"*); comparison/diff **DOES NOT EXIST**; shadow/dual execution **DOES NOT EXIST**; canary/% routing **DOES NOT EXIST**; decision-replay **DOES NOT EXIST** (state-replay exists — `nexus_infra/projections.py`); decision/feature rollback **DOES NOT EXIST** (only transaction/allocation rollback). **Reusable:** v2 correlation+causation+sequence (`nexus_core/domain/event.py:36-53`), v2 state-replay (`projections.py`, `event_store.py:140`), v1's transactional `communication_outbox` as a dual-write template (`gateway/communication_outbox.py:129-250`), v1's correlation-indexed `AuditLogRecord` ledger (`memory/models.py:184-199`), and the pydantic `NexusSettings` / versioned `SystemPolicyRecord` as a flag host (`config.py:178`, `models.py:579`).

**[RECOMMENDATION — one strategy] Adopt "Recorded Shadow Adjudication per Constitutional Owner":** an enhanced five-stage model that (1) shadows at the **constitutional owner boundary** (decomposing v1's conflated decisions), (2) records every v1 decision, v2 shadow decision, and their diff as **events in the ADR-007 durable log** (INV-13/17), (3) compares by **determinism class** (exact match for rule/config decisions; equivalence-band/semantic/human-adjudicated for the four LLM decisions), (4) guarantees shadow is **side-effect-free** (INV-29), and (5) is **flag-gated and reversible per owner**. Migrate in the order forced by the Policy-leaf rule: **Policy Engine first**, then Intent Resolution, Engineering Intelligence, Orchestration (runtime selection), Recovery (retry), Human Interaction (channel/approval surface), then the remainder. Reject big-bang cutover, flag-only rollout, exact-match-only shadow, and a forked parallel product (§ Recommendation).

**[FACT] Two migrations that are *new builds*, not relocations, and ADR-008 must flag them:** (a) **Risk/autonomy classification does not exist in v1** — the Discord "Risk Level" is a hardcoded `"LOW"` string (`communication/discord/bot.py:43`; producers `chat/executor.py:194,269,283`); its constitutional owners (EI proposes autonomy `:312`, Policy gates `:319`) have nothing to shadow against. (b) **Execution retry/recovery does not exist in v1** — failed executions go straight to FAILED (`execution/service.py:207`); only *notification* retry exists (`communication_outbox.py:244`). Recovery's retry ownership (INV-22, `:321`) is a greenfield build.

---

## 2. Current Decision Landscape  *(all [FACT], source-verified)*

**Two pipelines.** (a) **Conversation:** Discord adapter → `ChatService` (Planner → Validator → Executor). (b) **Work:** slash/chat action → `TaskService` → `EventGateway` → `WorkflowOrchestrator` → `ApprovalService` → `GovernanceManager` → `RuntimeRegistry` → `SandboxManager` → runner. Notifications flow through two outbox loops.

**The decision clusters that matter for migration** (full 44-row inventory in §6):

- **Intent parsing (non-deterministic).** `planner.py:109-158` turns a message into a typed `ChatAction{type,payload,confidence,requires_owner,requires_approval}` via a free-tier LLM; degrades to plain REPLY on failure. One deterministic override: `looks_like_email_request` regex forces `SEND_EMAIL` (`planner.py:43-46`).
- **Governance/policy (deterministic, spread across 4 sites).** Action-policy stamp table (`planner.py:63-70`); validator owner+approval gate (`validator.py:39-56`); the 11-check execution gate (`governance.py:60-653` — health, allowed-runtimes, runtime-policy match, active approval, repo containment, repo-active, runtime-on-repo, profile-on-repo, owner∈repo-owners, concurrency semaphore, branch allow/block/protect, command blacklist); policy resolution registry→default→fail-closed (`policy_service.py:54-95`).
- **Runtime selection (deterministic, hardcoded).** Per-action constants: research→`"nexus"` (`chat/executor.py:29`), default task→`"gemini"` (`task_service.py:61`); adapter resolution via `RuntimeRegistry.get_adapter_cls` (`runners/__init__.py:24-69`).
- **Approval (deterministic).** `ApprovalService.evaluate_approval` owner-authorized, fail-closed on empty owner set (`approvals/service.py:85-189`); Discord `ApprovalView` surfaces the decision (`discord/bot.py:75-104`); gate check before start (`execution/service.py:41-45`).
- **Retry/dead-letter (non-deterministic — notifications only).** `communication_outbox.py:129-250`: lease → deliver → on failure retry with `10*2^n + random.uniform(0,5)` backoff, dead-letter at `max_attempts`.
- **Channel routing (deterministic, split).** `ChannelRouter` role↔channel table (`channels.py:99-157`) **but** the send side uses hardcoded channel keys (`bot.py:284-315`, `outbox.py:28-159`) that bypass the router — two mechanisms, no single owner.
- **Scheduler (deterministic, config).** Job enablement + triggers (`scheduler.py:111-196`); coalesce/misfire/max-instances constants (`:64-95`); job-skip (`jobs.py:98-119`).
- **Risk/autonomy: absent.** Hardcoded `"LOW"` (see §1).

**[FACT] No decision is logged as an input→output pair for comparison.** The richest trail is `governance.py:_write_audit` (`:39-58`), which writes an `AuditLogRecord` per governance branch with the inputs it evaluated — a single-path audit, not a two-engine comparison. `policy_service.py:77` names a "Phase 1 Dual-Read/Fallback behavior" but that is registry-else-default *fallback*, not shadow comparison.

---

## 3. Constitutional Ownership Mapping

**[FACT]** Mapping every v1 decision cluster to its sole constitutional owner (`ARCHITECTURE_CONSTITUTION.md:307-329`), with conflicts flagged.

| v1 decision (source) | Constitutional owner (basis) | Note / conflict |
|---|---|---|
| Intent→ChatAction **type** (`planner.py:109`) | **Intent Resolution** (Understand) — `:309` INV-08 | v1 fuses 3 owners here ⚠ |
| Implied **kind of work** (in the same call) | **Engineering Intelligence** (classification) — `:310` [ADR-005] | must be *decomposed out* of planner ⚠ |
| `_ACTION_POLICY` **approval-required** stamp (`planner.py:63`) | **Policy Engine** — `:319` INV-28/30 | policy currently in the planner ⚠ |
| Validator owner/approval gate (`validator.py:39`) | **Policy Engine** — `:319` | policy spread site 2 ⚠ |
| 11-check execution gate (`governance.py:60`) | **Policy Engine** — `:319` INV-28 (sole evaluator) | policy spread site 3 ⚠ |
| Policy registry→default (`policy_service.py:54`) | **Policy Engine** — `:319`; Policy object `:366` | the executable core to converge |
| Runtime/adapter selection (`chat/executor.py:29`, `runners/__init__.py:24`) | **Orchestration** — `:316` INV-37 | v1 hardcodes; Orchestration must own |
| Approval **required?** (gates above) | **Policy Engine** — `:319` INV-28 | vs. |
| Approval **outcome** (`approvals/service.py:130`, `discord/bot.py:75`) | **The approver, surfaced by Human Interaction** — `:320` INV-29 | split required?/outcome cleanly |
| Retry/dead-letter (`communication_outbox.py:244`) | **Recovery** (retry whether/bounds) — `:321` INV-22 | v1 has it for *notifications only* |
| Execution retry | **Recovery** — `:321` | **void in v1** (new build) ⚠ |
| Channel routing (`channels.py:99` + hardcoded `bot.py:284`) | **Human Interaction** (reach the human) — `:328` INV-34; notification side → **Operations** `:329` | v1 split across 2 mechanisms ⚠ |
| Scheduler enablement/triggers (`scheduler.py:111`) | **Operations** (operational cadence) — `:329` [void] / Orchestration enacts | scheduler is Operations-owned cadence |
| Task state-machine (`task_service.py:25`) | **Orchestration** (lifecycle) — via `:318` pause/resume/cancel | state = projection under ADR-001 |
| Completion (finalize status `service.py:200`) | **Validation** — `:324` INV-20/21 | v1 has no separate validation verdict ⚠ |
| Risk/autonomy (hardcoded LOW) | **EI proposes** `:312` + **Policy gates** `:319` | **void in v1** (new build) ⚠ |
| Research importance score (`research.py:561`) | **Operations/Knowledge** ranking (out of core spine) | LLM; off critical path |

**[FACT] Conflicts to resolve in ADR-008 / downstream ADRs:**
1. **Owner conflation** — `planner.py` decides Intent + Classification + approval-required in one place; migration must split it across Intent Resolution, EI, and Policy Engine (decomposition map required).
2. **Policy dispersion** — four policy sites (`planner`, `validator`, `governance.py`, `policy_service`) must converge to the single Policy Engine (INV-28 sole evaluator).
3. **Channel routing split** — `ChannelRouter` vs. hardcoded channel keys; Human Interaction must become the single owner of "reach the human."
4. **Two voids masquerading as migrations** — risk/autonomy and execution-retry have no v1 implementation to shadow; they are greenfield builds with a constitutional owner.
5. **Required-vs-outcome approval** — v1 blends the "is approval required" gate with the "what did the approver decide" outcome; the Constitution splits them (Policy Engine `:319` vs approver/Human Interaction `:320`).

---

## 4. Shadow Migration Model

### 4.1 Is the generic model sufficient?
**[FACT]** The proposed model is *Current → Shadow (v1+v2 compute, log diff) → Canary (small %) → Default (v2 authoritative) → Removal (v1 deleted)*.

**[RECOMMENDATION] Verdict: sound skeleton, insufficient as written.** Three evidence-backed gaps:

1. **Exact-match comparison breaks on non-deterministic decisions.** v1's primary decision is an LLM classification (`planner.py:109`, temp 0.2). Two engines will *legitimately* differ token-by-token while being semantically equivalent. A naive "log difference" would emit a false-mismatch storm and could trigger spurious rollbacks. **The model must compare by determinism class.**
2. **v1 conflates owners, so 1:1 shadowing is impossible.** You cannot shadow "`planner.py` → EI" because `planner.py` also owns Intent and approval-stamp. **The model needs a decomposition map that shadows at the constitutional boundary**, feeding the same v1 inputs to each of the (Intent Resolution, EI, Policy) shadows.
3. **Shadowing must be recorded and side-effect-free.** Per ADR-001/ADR-007 the decision, shadow, and diff must be **events in the durable log** (INV-13/17) so mismatches are replayable and provable; and shadow computation must **never actuate** (INV-29 — Governance authorizes, never executes). The generic model omits both.

### 4.2 Recommended model — Recorded Shadow Adjudication per Constitutional Owner
**[RECOMMENDATION]** Per owner *O* migrating from its v1 site(s) to its v2 subsystem:

```
Stage 0  INSTRUMENT   v1 emits a DecisionRecord event at O's boundary:
                      {decision_id, owner=O, engine=v1, version, inputs(hash+ref), output, correlation_id}
                      (reuse governance _write_audit + ChatAction/ValidationResult typed boundaries;
                       write to the ADR-007 durable log, tagged with v2 correlation+causation)
   │
Stage 1  SHADOW       v2 O computes from the SAME recorded inputs, side-effect-free;
                      emits a paired ShadowDecision event (engine=v2). A Comparator emits a
                      DecisionDiff event classified by determinism class:
                        • deterministic (rule/config) → exact-match verdict
                        • non-deterministic (LLM)      → equivalence-band / semantic / human-adjudicated
                      v1 remains authoritative. No cohort yet.
   │
Stage 2  CANARY       Flag-gated: for a small cohort, v2's decision becomes authoritative;
                      v1 runs in REVERSE shadow (still compared). Cohort defined by a stable
                      key (owner-flagged users / hashed correlation bucket).
   │
Stage 3  DEFAULT      v2 authoritative for all traffic; v1 shadows as a safety net; diffs still recorded.
   │
Stage 4  REMOVAL      Delete v1 site for O once the per-owner exit gate holds for a bake period
                      (§10). INV-07 dual-representation exception closes for O.
```

**[FACT] Reusable substrate that makes this cheap:** v2 correlation+causation+sequence already exist (`event.py:36-53`) to bind a v1 decision to its v2 shadow under one stream; v2 state-replay (`projections.py`) becomes decision-replay when the DecisionRecord events are in the log; v1's `AuditLogRecord` (correlation-indexed, `models.py:197`) is the Stage-0 instrumentation sink until the durable log lands; `NexusSettings`/`SystemPolicyRecord` host the per-owner flags.

**[FACT] Migration order (forced, not chosen):** the Policy-leaf rule (`:297-299`) means every other governed decision depends on Policy; therefore **Policy Engine migrates first** (consistent with `IMPLEMENTATION_READINESS_REVIEW.md:298` C6 and the Engineering Program P2). Then the decision-flow order (`:396`): Intent Resolution → Engineering Intelligence → Orchestration(runtime) → Recovery(retry) → Human Interaction(channel/approval surface) → Validation → the rest.

---

## 5. Hidden Architectural Decisions ADR-008 Must Settle  *(each evidence-anchored)*

1. **Decision identity.** *Evidence:* `ChatAction` carries no id (`chat/planner.py:152`); v1 correlation is per-message not per-decision (`core/events.py:36`). *Decide:* a stable `decision_id` scheme that pairs a v1 decision with its v2 shadow.
2. **Decision versioning.** *Evidence:* policy rows are versioned (`models.py:583`); events carry `version`/`schema_version` (`nexus_core/domain/event.py:31,49`). *Decide:* how a decision-engine version is stamped so a diff is attributable to a specific v2 revision.
3. **Comparison strategy by determinism class.** *Evidence:* 4 LLM decisions vs 40 rule/config (§2). *Decide:* exact-match for deterministic; equivalence-band/semantic/human-adjudicated for LLM decisions, with the band defined per decision.
4. **Shadow recording medium.** *Evidence:* durable log is being built by ADR-007; `AuditLogRecord` exists now (`models.py:184`). *Decide:* DecisionRecord/ShadowDecision/DecisionDiff are events in the ADR-007 log (**hard dependency on ADR-007**).
5. **Replay ownership.** *Evidence:* state-replay exists (`projections.py:81`); decision-replay does not. *Decide:* who owns re-running a recorded decision against recorded inputs (a Comparator/adjudication component), and that it is deterministic for rule decisions.
6. **Mismatch handling.** *Evidence:* no mismatch handler exists. *Decide:* on a Stage-1/2 diff — record only, alert, block, or auto-rollback — as a function of severity × owner.
7. **Rollback trigger.** *Evidence:* no decision-rollback exists (only txn/allocation, `unit_of_work.py:108`, `runtime_manager.py:279`). *Decide:* the diff-rate/severity threshold and bake period that flips a flag back.
8. **Feature-flag host + granularity.** *Evidence:* no flag store; `NexusSettings` (`config.py:178`) and versioned `SystemPolicyRecord` (`models.py:579`) are candidates. *Decide:* per-constitutional-owner flags, their host, and runtime-mutability (no redeploy).
9. **Canary cohort definition.** *Evidence:* `is_owner`/`is_dm` metadata exist (`discord/bot.py`); no cohorting. *Decide:* cohort key (owner-flag, hashed-correlation bucket, or %) and its stability across a session.
10. **Side-effect isolation in shadow.** *Evidence:* INV-29 (Governance authorizes, never executes); shadow must not actuate. *Decide:* the mechanism guaranteeing v2 shadow performs no external effect (no outbox write, no runner spawn).
11. **Decomposition map.** *Evidence:* `planner.py:109` fuses Intent+EI+Policy. *Decide:* the explicit mapping from each conflated v1 decision to the set of v2 owners it shadows.
12. **Correlation binding.** *Evidence:* v1 corr-id (`core/events.py:36`) vs v2 corr+causation (`event.py:36-53`). *Decide:* how a v1 decision and its v2 shadow share one correlation stream so diffs are replayable (INV-39).
13. **Per-owner exit gate + INV-07 window.** *Evidence:* Readiness `:212` (bounded dual-representation acceptable if declared). *Decide:* the measurable per-owner gate and the time-boxed coexistence-then-delete window.
14. **Greenfield-owner handling.** *Evidence:* risk/autonomy and execution-retry are voids (§1). *Decide:* how an owner with no v1 counterpart is introduced (shadow against a null/hardcoded baseline, then default) without a comparison partner.

*(No invented decisions — each cites source. Snapshot cadence, durable format, and sync/async are ADR-007's, not ADR-008's.)*

---

## 6. Migration Inventory

**[FACT + RECOMMENDATION]** Complete inventory. *Difficulty* and *order* are recommendations grounded in the evidence columns. Order bands: **B0** = enabling substrate; **B1** = Policy (leaf, first); **B2** = entry/reasoning; **B3** = execution ownership; **B4** = recovery/human; **B5** = periphery.

| Decision (v1 source) | Constitutional owner | Difficulty | Order | Rollback complexity | Dependencies |
|---|---|---|---|---|---|
| *Substrate: flags, DecisionRecord logging, Comparator, shadow harness* | (enabling) | High | **B0** | Low (flag off) | ADR-007 durable log |
| Policy resolution (`policy_service.py:54`) | Policy Engine | Med | **B1** | Low | B0; ADR-007; ADR-009(policy) |
| 11-check governance gate (`governance.py:60`) | Policy Engine | **High** | **B1** | Med (blocks execution) | Policy core; repo-understanding |
| Approval-required stamp (`planner.py:63`, `validator.py:39`) | Policy Engine | Med | **B1** | Low | Policy core |
| Command blacklist / concurrency / branch checks (`governance.py:259-642`) | Policy Engine | Med | **B1** | Med | Policy core |
| Intent→action type (`planner.py:109`) | Intent Resolution | **High** (LLM) | **B2** | Med | B0; decomposition map; semantic comparator |
| Kind-of-work classification (in `planner.py`) | Engineering Intelligence | **High** (LLM) | **B2** | Med | Intent shadow; ADR-005 |
| Risk/autonomy (**void**, hardcoded LOW) | EI (propose) + Policy (gate) | High (greenfield) | **B2** | Low | EI + Policy live |
| Runtime/adapter selection (`chat/executor.py:29`, `runners/__init__.py:24`) | Orchestration | Med | **B3** | Med (wrong runtime) | Registry unification (ADR-009) |
| Task state-machine / lifecycle (`task_service.py:25`) | Orchestration | Med | **B3** | Med | ADR-007 (state=projection) |
| Completion verdict (`service.py:200`) | Validation | Med | **B3** | Low | Orchestration |
| Approval outcome (`approvals/service.py:130`, `discord/bot.py:75`) | Approver / Human Interaction | Med | **B4** | Med (human gate) | Policy(required?); HI surface |
| Retry/dead-letter notifications (`communication_outbox.py:244`) | Recovery | Med | **B4** | Low | Recovery engine |
| Execution retry (**void**) | Recovery | High (greenfield) | **B4** | Low | Recovery live |
| Channel routing (`channels.py:99` + hardcoded `bot.py:284`) | Human Interaction / Operations | Med | **B4** | Low | HI single-owner consolidation |
| Scheduler cadence (`scheduler.py:111`) | Operations | Low | **B5** | Low | Operations subsystem |
| Notification event→channel (`outbox.py:28`) | Operations / Human Interaction | Low | **B5** | Low | outbox seam |
| Research importance score (`research.py:561`) | Operations/Knowledge (off-spine) | Low (LLM) | **B5** | Low | none critical |
| Priority-feed threshold (`feed.py:40`) | Operations | Low | **B5** | Low | score above |
| Briefing dedup/targeting (`briefing.py:112`) | Operations | Low | **B5** | Low | outbox |

---

## 7. Failure Modes

**[FACT]** Per stage: what fails · detection · rollback · evidence preserved · protecting invariant.

| Stage | What can fail | Detection | Rollback | Evidence preserved | Invariant |
|---|---|---|---|---|---|
| 0 Instrument | Instrumentation perturbs v1 (latency, exception) | v1 latency metric regress; error rate (`metrics.py`) | Remove instrument (additive, no logic change) | DecisionRecord events in log | INV-13 (append-only) |
| 0 Instrument | Inputs not fully captured → non-replayable | Replay of a DecisionRecord ≠ v1 output | Fix capture; re-instrument | partial records flagged | INV-17 (record-as-data) |
| 1 Shadow | v2 shadow throws / diverges | DecisionDiff event; diff-rate dashboard | None needed — v1 still authoritative | v1 + v2 + diff events | INV-29 (shadow can't act) |
| 1 Shadow | False mismatch on LLM decision (exact-match misuse) | diff class = "exact" on a non-deterministic owner | Switch comparator to band/semantic | classified diff events | INV-17 |
| 1 Shadow | Shadow causes a side effect | outbox/runner event with shadow correlation id | Kill shadow flag; the effect is the bug | correlated event trail | INV-29 |
| 2 Canary | v2 wrong for the cohort | DecisionDiff (reverse shadow) + cohort SLO | Flip owner flag → v1 authoritative | both engines' events | INV-28/23 (owner integrity) |
| 2 Canary | Cohort instability (user flips buckets mid-session) | correlation shows engine change within a stream | Pin cohort by stable key | correlation stream | INV-39 |
| 3 Default | Latent divergence at scale | v1 safety-net shadow diff-rate | Flip flag → v1 | full diff history | INV-13/17 |
| 4 Removal | v1 deleted while still referenced | import/grep guard; smoke test | Revert deletion PR (atomic) | git history + log | INV-07 (converge-then-delete) |
| any | Policy migrated wrong (governance regression) | v1-vs-v2 verdict diff (Policy shadow) | Policy is B1 & flag-gated → flip to v1 | policy decision events | INV-28/30 (fail-closed) |

**[FACT] Two structural failure risks unique to this migration:**
- **Owner-conflation leakage:** shadowing `planner.py` as one unit would attribute a diff to the wrong owner. *Detection:* decomposition map assigns each diff to exactly one owner; a diff with no single owner is a map defect. *Invariant:* INV-02.
- **Greenfield owners have no comparison partner** (risk/autonomy, execution-retry): they cannot be "equivalence-validated" against v1. *Handling:* shadow against the documented v1 baseline (hardcoded LOW; no-retry) and gate on *behavioral* acceptance, not equivalence.

---

## 8. Rollback Strategy

**[FACT] Decision/feature rollback does not exist today** — only DB-transaction rollback (`database.py:156-182`, `unit_of_work.py:108`) and resource-allocation rollback (`runtime_manager.py:279`). It must be built.

**[RECOMMENDATION]** Rollback is a **flag flip per constitutional owner**: each owner's authority is gated by a runtime-mutable flag (hosted in `NexusSettings` or the versioned `SystemPolicyRecord`). Rolling an owner back = set its flag to `v1`, and v1 immediately recomputes because Stage 0 never removed the v1 site until Stage 4. Because every decision, shadow, and diff is a recorded event (INV-13/17), rollback **loses no evidence** and the reason for rollback is itself a queryable diff history.

Properties required (ADR-008 to specify): (a) rollback is **atomic and instantaneous** (single flag write, no redeploy); (b) rollback is **owner-scoped** (never a global revert — a consenting migration of one owner must not widen or narrow another); (c) rollback of **Policy** is privileged and defaults-safe (a bad policy engine flips to v1's fail-closed defaults, `policy_service.py:63-69`); (d) Stage-4 removal is the *only* irreversible step and is gated on a bake period (§10) plus an atomic-revert deletion PR.

---

## 9. ADR-008 Questions

1. What is the **`decision_id` / versioning** scheme that pairs a v1 decision with its v2 shadow and attributes diffs to a v2 revision? *(H1, H2)*
2. What is the **comparison strategy per determinism class**, and the equivalence band for each of the four LLM decisions? *(H3)*
3. Are DecisionRecord/ShadowDecision/DecisionDiff **events in the ADR-007 durable log**, and what is the interim sink before it lands? *(H4 — declares the ADR-007 dependency)*
4. Who **owns decision-replay/adjudication**, and is it deterministic for rule decisions? *(H5)*
5. What is the **mismatch-handling policy** (record / alert / block / auto-rollback) by severity × owner? *(H6)*
6. What **diff-rate/severity threshold + bake period** triggers rollback, and what is the per-owner **exit gate**? *(H7, H13)*
7. What **hosts the per-owner flags**, at what granularity, and is it runtime-mutable without redeploy? *(H8)*
8. How is the **canary cohort** defined and kept stable across a session? *(H9)*
9. How is **shadow side-effect isolation** guaranteed (no outbox, no runner spawn)? *(H10, INV-29)*
10. What is the **decomposition map** from each conflated v1 decision to its set of v2 owners? *(H11)*
11. How do v1 and v2 decisions **share a correlation stream** for replayable diffing? *(H12)*
12. How are **greenfield owners** (risk/autonomy, execution-retry) introduced without a v1 comparison partner? *(H14)*
13. In what **order** do owners migrate, and does it honor the Policy-leaf rule (Policy first)? *(governance dependency `:297-299`)*
14. What is the **declared, time-boxed INV-07 coexistence exception** per owner and its converge-then-delete exit? *(H13; Readiness `:212`)*

---

## 10. Exit Criteria for Approving ADR-008

ADR-008 may be marked **Accepted** only when **all** hold:

1. **All fourteen questions in §9 are answered** in the ADR, each a single decision (no "Unresolved" section).
2. **The ADR-007 dependency is explicit:** DecisionRecord/ShadowDecision/DecisionDiff are events in the durable log ADR-007 defines; ADR-008 does not proceed to Stage 1 for any owner before that log exists.
3. **A decomposition map is attached** resolving every owner-conflation in §3 (at minimum `planner.py` → {Intent Resolution, EI, Policy}, and the four policy sites → Policy Engine).
4. **The comparison strategy is proven on one deterministic and one non-deterministic owner:** a spike shows exact-match works for a rule decision (e.g. policy verdict vs v1 `policy_service`) and an equivalence-band/semantic verdict works for an LLM decision (e.g. intent type), with no false-mismatch storm.
5. **Side-effect isolation is demonstrated:** a shadow run emits DecisionDiff events but **zero** outbox/runner events under its correlation id (INV-29 guardrail).
6. **Per-owner rollback is demonstrated:** flipping an owner's flag returns authority to v1 atomically, no redeploy, with the full decision/diff history preserved (INV-13/17).
7. **Migration order honors the Policy-leaf rule:** Policy Engine is scheduled first; no governed owner defaults-on before Policy is authoritative.
8. **Greenfield owners have a defined path:** risk/autonomy and execution-retry are introduced against a documented baseline with a behavioral acceptance gate, not an equivalence gate.
9. **Every stage is releasable and reversible:** each owner is flag-gated, default-safe (v1 authoritative until proven), with a declared time-boxed INV-07 window and an atomic-revert removal PR.
10. **Sign-off** from the deciders of record (Architecture Review Board, per `adr/ADR-001.md`).

---

### Fact / Assumption / Recommendation ledger (summary)
- **[FACT]** 44 v1 decisions enumerated from source; 4 are LLM/non-deterministic; v1 conflates Intent+EI+Policy in `planner.py` and spreads policy across 4 sites; flags/decision-logging/diff/shadow/canary/decision-replay/decision-rollback **do not exist**; correlation+state-replay+outbox+config-host are reusable; risk/autonomy and execution-retry are v1 voids; the Constitution fixes one owner per decision and makes Policy the universal leaf.
- **[ASSUMPTION]** LLM decisions can be adjudicated by an equivalence band/semantic check acceptable to the Architecture Review Board; the `SystemPolicyRecord` versioned store is a suitable runtime flag host. Both to be *confirmed* by the §10.4 spike.
- **[RECOMMENDATION]** Recorded Shadow Adjudication per Constitutional Owner (decompose at the constitutional boundary; record decision+shadow+diff as durable events; compare by determinism class; side-effect-free; flag-gated per-owner rollback), sequenced Policy-first. Reject: **big-bang cutover** (product must stay live, no reversibility), **flag-only rollout** (no pre-cutover equivalence evidence — blind), **exact-match-only shadow** (false-mismatch storm on the 4 LLM decisions), **forked parallel v2 product** (two products, unbounded INV-07 divergence), and **per-decision migration ignoring the Policy leaf** (governance dependency inversion).

*This spike changed production code: none. Commits: none.*
