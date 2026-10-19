# ADR-v1.0.1-alignment-release: Nexus v1.0.1 "Alignment" Declared STABLE

Date: 2026-06-24
Status: Accepted
Release: v1.0.1 · Codename: Alignment
Related: NEXUS_FIRST_IMPRESSION.md (v1.0.0 audit), ADR-scheduler-foundation, ADR-nexus-reality-audit,
ADR-sandbox-safety-review, `blueprint/implementations/v1.0.1/v1.0.1-alignment-summary.md`
Supersedes: none (closes the v1.0.1 finding set A-001…A-006)

---

## Context

The accepted v1.0.0 onboarding audit (maturity 6.0/10) produced six findings: A-001 fail-open owner
auth, A-002 execution-timeout mismatch, A-003 missing scheduler, A-004 documentation drift, A-005 Nexus
simulated behavior, A-006 default-host sandbox. v1.0.1 "Alignment" was chartered as a correctness,
safety, and operational-completeness release — explicitly **not** a feature release — with the rule that
every change trace to an accepted finding, carry validation + an ADR/report, and keep the blueprint
synchronized. Work proceeded as gated Action Points AP-101 (validation) → AP-102 (A-001/A-002 fixes) →
AP-103 (scheduler design + impl) → AP-104 (documentation alignment) → AP-105 (Nexus audit) → A-006
(sandbox audit), each accepted before the next.

## Decision

**Declare Nexus v1.0.1 "Alignment" STABLE** as a single-operator, attended-to-lightly-autonomous,
governed-execution control plane, and **close the v1.0.1 finding set (A-001…A-006).**

Specifically:
1. **A-001, A-002, A-003 are resolved by implementation** (fail-closed auth; ADR-010 timeouts with
   hard-limit clamp; single-node APScheduler with six audited jobs), under TDD, with 143 tests passing
   and ruff/mypy clean, no regressions.
2. **A-004 is resolved by documentation alignment** with a single authoritative status source
   (`architecture-status-summary.md`); doc accuracy ~3.0→9.0/10.
3. **A-005 and A-006 are resolved as findings** by evidence-based audits that established reality —
   Nexus = **Prototype**, sandbox = **Unsafe By Default** — **without** code change, per their
   audit-only mandate. Their remediation is explicitly **future-AP** work.
4. The **STABLE** designation applies to the governed core + single-node autonomy layer. It is **not** a
   claim of default-secure sandboxing, full autonomous multi-runtime operation, or multi-node operation.

## Consequences

**Positive**
- Nexus is now honest, aligned, and operationally complete for single-node operation: safer core
  (fail-closed, correct timeouts), autonomy engines actually triggered, truthful documentation, and the
  two soft spots precisely bounded rather than overstated.
- Overall maturity rises 6.0 → 7.0/10; operational maturity ~3–4 → 6.5; documentation ~3.0 → 9.0.
- A clean, evidence-backed historical record (5 closure deliverables + per-finding ADRs/reports) exists
  for the release.

**Negative / accepted**
- Two **Critical** residual risks remain by design — sandbox host execution by default and fail-open
  provider resolution — mitigated by deliberate Docker configuration + the approval gate + audit, and
  documented as the operator's responsibility until a future hardening AP.
- Nexus remains a Prototype and Gemini/Claude remain Stubbed; "multi-runtime execution" is
  architecturally real but functionally shallow.
- Code-scoped residual debt persists unfixed (in-code version string, `/api/v1/status`/health, Alembic),
  logged in the risk register as Deferred.

**Operating baseline going forward**
- Configure `discord.owner_ids` (mandatory), run exactly one instance, and enable Docker sandboxing for
  any untrusted workload; otherwise treat deployments as host-executing and attended.
- The authoritative subsystem status is `architecture-status-summary.md`; future status claims must agree
  with it. Any upgrade to Nexus/sandbox classification requires new code + new evidence, not intent.

## Closure

The v1.0.1 "Alignment" release is **complete**. All six findings are addressed; the mission — *make Nexus
honest, aligned, and operationally complete* — is achieved. Next substantive work items are the
evidence-backed future APs enumerated in `v1.0.1-alignment-summary.md` (Future Work), to be chartered and
gated separately.
