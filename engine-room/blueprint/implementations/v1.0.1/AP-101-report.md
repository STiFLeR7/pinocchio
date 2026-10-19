# AP-101 — Audit Validation — Implementation Report

> **Release:** Nexus v1.0.1 "Alignment"
> **Action Point:** AP-101 — Audit Validation
> **Type:** Investigation / validation (systematic-debugging Phase 1). **No code changed.**
> **Status:** ✅ Complete
> **Primary artifact:** [`alignment-validation.md`](./alignment-validation.md)
> **Source state:** commit `aa3e527`, tag `v1.0.0`, branch `master`.

---

## 1. Objective

Per the v1.0.1 work sequence, AP-101 requires verifying **every** accepted audit finding (A-001…
A-006) before any implementation, and producing `alignment-validation.md` with — for each finding —
Source Evidence, Risk, Impact, Fix Strategy, and Validation Strategy. **No implementation in this
AP.**

This maps to **Phase 1 of systematic debugging** (root-cause investigation): establish first-hand
evidence and root cause before any fix. The Iron Law — *no fixes without root-cause investigation* —
is satisfied by completing this AP first.

## 2. Method

- Re-read the actual source for each finding **independently** of the prior onboarding subagent
  reports (those reports are evidence, but AP-101 is a fresh verification).
- Files read first-hand this AP: `nexus/approvals/service.py`, `nexus/config.py`, `nexus/api.py`,
  `nexus/execution/runners/claude.py`, `nexus/execution/runners/gemini.py`,
  `nexus/execution/runners/nexus.py`, `nexus/execution/sandbox/manager.py`,
  `nexus/execution/sandbox/provider.py`, `README.md`.
- Static searches: scheduler-symbol sweep over `nexus/`; engine-entrypoint location; dependency
  confirmation in `pyproject.toml`/`uv.lock`.
- One **read-only runtime proof** for A-002 (executed `ExecutionConfig` field introspection — no
  files modified).

## 3. Results — validation verdicts

| Finding | Priority | Verdict | Key first-hand evidence |
|---|---|---|---|
| A-001 Fail-open owner auth | P0 | **CONFIRMED** | `config.py:42` (`owner_ids=[]`); `approvals/service.py:94` (`if self.owner_ids and …`); no startup gate in `api.py:65-137` |
| A-002 Execution timeout mismatch | P0 | **CONFIRMED (runtime-proven)** | `config.py:83-88` (no `research_timeout_seconds`); `claude.py:83`/`gemini.py:88` read it → 300; runtime: `hasattr(...)==False`; `hard_limit` never enforced |
| A-003 Missing scheduler | P1 | **CONFIRMED + NUANCE** | apscheduler installed (`uv.lock:182`); 0 scheduler symbols in `nexus/`; 4 engine entrypoints uncalled; 2 required jobs (outbox/checkpoint health) have no existing code |
| A-004 Documentation drift | P2 | **CONFIRMED** | `README.md:5-7,144-161` (pre-alpha/0.1.0/all phases Pending); `STATUS.md:58-68`; `ROADMAP.md:115-275` vs git tag v1.0.0 |
| A-005 Nexus simulated | P3 | **CONFIRMED** | `nexus.py:7` (`AsyncMock` import); `:184-209` (sim branch); `:145-149` (hardcoded plan); `:76-86` (canned search); `:310-312` (no-op terminate) |
| A-006 Sandbox host execution | P4 | **CONFIRMED + NUANCE** | `config.py:101` (`enabled=False`); `manager.py:44-45`→`provider.py:96-101` (host shell); Docker failure re-raises (no host fallback); unknown-provider → Local footgun (`manager.py:52-53`) |

Full per-finding detail (Root Cause, Risk, Impact, Fix Strategy, Validation Strategy, Constraint
Trace) is in `alignment-validation.md`.

## 4. Material nuances surfaced (carry forward)

1. **A-001 has no startup enforcement point today** — `ApprovalService` is built per-event inside
   the orchestrator, so the "startup must fail" target requires a **new startup gate in
   `api.py:lifespan`** plus a defense-in-depth deny-all in the service. (AP-102)
2. **A-002 is a double defect** — wrong attribute name *and* wrong per-runtime mapping, and
   `hard_limit` is unenforced. The fix must address all three across **all three** runtime paths
   (Claude/Gemini/Nexus). (AP-102)
3. **A-003 requires two genuinely new monitor jobs** (outbox health, checkpoint health) with no
   existing implementation — the only real "no new features" tension in v1.0.1. Must be scoped as
   read-only health observation and **approved at AP-103 design** before implementation. (AP-103)
4. **A-006's accepted target is a configuration audit, not a behavior change.** No default flip is
   authorized by the finding as written; the path matrix is captured in `alignment-validation.md`.
   Note the unknown-`provider` → host fallback footgun.
5. **A-005 is audit-only** (AP-105). The sole Nexus *code* change in v1.0.1 is the shared A-002
   timeout path; cross-referenced between AP-102 and AP-105.

## 5. Constraint compliance (v1.0.1 operating constraints)

- ✅ No new features (this AP changed nothing).
- ✅ No architecture/runtime/governance redesign.
- ✅ Every finding's fix strategy traces directly to an accepted finding (constraint-trace recorded
  per finding).
- ✅ Validation strategy defined for every finding (constraint 8).
- ✅ This report + `alignment-validation.md` provide the required documentation (constraint 9).
- ✅ Blueprint synchronized for AP-101 scope (this folder); broader doc sync is AP-104.

## 6. Deliverables produced

- `blueprint/implementations/v1.0.1/alignment-validation.md` — per-finding validation (mandated).
- `blueprint/implementations/v1.0.1/AP-101-report.md` — this report.

## 7. Exit criteria

- [x] Every accepted finding re-verified with first-hand source evidence.
- [x] Root cause established for each (not just symptom).
- [x] Fix + validation strategy defined and constraint-traced for each.
- [x] No implementation performed.
- [x] Deliverables written under `blueprint/implementations/v1.0.1/`.

## 8. Recommendation

Proceed to **AP-102 — Critical Safety Fixes (A-001, A-002)** under TDD (systematic-debugging Phase 4:
write the failing test that reproduces each defect, then the minimal fix). Hold AP-103 implementation
until `scheduler-design.md` is approved. AP-104 (docs) and AP-105 (Nexus audit) may proceed in
parallel as they are documentation/evidence-only.

> Awaiting authorization to begin AP-102. Per instruction, AP-101 only was performed this step.
