# ADR-sandbox-pilot-safe: Execution Sandbox Reclassified Experimental → Pilot Safe

Date: 2026-06-24
Status: Accepted
Release: v1.1.0 "Containment" · Track S Closure (S-2 / S-3 / S-4)
Supersedes (classification only): ADR-sandbox-safety-review ("Unsafe By Default")
Related: ADR-sandbox-v1.1-foundation, ADR-nexus-reality-audit, ADR-011-local-first-deployment,
ADR-010-execution-timeouts, `blueprint/implementations/v1.1.0/track-s-closure-review.md`,
`track-s-risk-matrix.md`, `track-s-before-after.md`

---

## Context

`ADR-sandbox-safety-review` (A-006) classified the execution sandbox **"Unsafe By Default"** on four
evidence-pinned facts: (1) the default config executed commands on the host silently; (2) unknown
provider names fell open to host; (3) the containment policy was decorative under Local with no startup
validation; (4) Nexus file tools bypassed containment entirely. It produced a 9-risk register
(R-01…R-09) and authorized **no remediation**.

Track S (separately authorized: S-2, S-3, S-4) remediated the Pilot-gating subset under strict TDD,
minimal diff, with no schema/scheduler/governance/event changes. This ADR records the formal
reclassification decision based on the closure review, which re-verified every claim against current
source and a live test/lint/type run.

**Evidence basis (all in-repo, re-verified live at HEAD `2fd3ffc`):**
- Source: `manager.py` (fail-closed resolution + `validate_sandbox_startup`), `provider.py`
  (`enforces_policy`, `ensure_available`, `RECOGNIZED_PROVIDERS`), `confinement.py`
  (`resolve_in_workspace`), `nexus.py` (file-tool confinement), `api.py` (lifespan gate),
  `exceptions.py` (three fail-closed exceptions).
- Tests: `test_sandbox_resolution.py` (9), `test_sandbox_enforcement.py` (14),
  `test_workspace_confinement.py` (12) — green within **178 passed**; ruff clean; mypy clean (58 files).

## Decision

**Reclassify the execution sandbox from Experimental ("Unsafe By Default") to "Pilot Safe."**

The four facts underpinning the "Unsafe By Default" label are each now reversed in code with test
evidence:

1. Default no longer runs on host — **fail-closed** at construction (R-01, R-02).
2. Unknown provider — **fail-closed**, no host fallback (R-02).
3. Policy enforcement is **honest** (`policy_enforced` flag/audit) and **boot-validated**
   (R-03, R-06, R-07).
4. Agent file tools are **workspace-confined**, fail-closed, provider-independent (R-05).

The six Pilot-gating risks (R-01, R-02, R-03, R-05, R-06, R-07) are **closed**; both Critical risks are
**eliminated**.

**Closure-review verdict: APPROVED.**

### Why Pilot Safe and not Production Safe

Three register items remain, all **outside the Track S charter**:
- **R-04** (bypassable command blacklist) — governance-owned; mitigated by the approval gate + audit +
  (when on) container isolation.
- **R-08** (shell-string exec surface) — design-inherent to "run approved commands"; bounded under
  Docker, host-only via deliberate warned opt-in.
- **R-09** (default `filesystem_policy=restricted`, not `readonly`) — partial; `:ro` available.

These are acceptable under **supervised pilot** conditions but not at the zero-residual bar of
Production Safe. Host execution also remains *possible* by deliberate, audited opt-in — appropriate for
a pilot, not for an unconditional production isolation claim.

## Conditions of the classification

1. **Pilot Safe, not Production Safe.** R-04, R-08, R-09 must be disclosed wherever the classification
   is cited.
2. **Effective on commit.** Track S source is currently staged but **uncommitted** (HEAD `2fd3ffc`).
   The classification is evidence-bound to that code; it takes effect when the Track S changes are
   committed.
3. **Documentation step is separate.** The authoritative status in `architecture-status-summary.md`
   (Sandbox: Experimental → Pilot Safe) is updated only via a separately authorized documentation
   action; this ADR and the closure review perform no such rewrite.
4. **Production isolation still requires** `sandbox.enabled=true`, `sandbox.provider=docker`, a present
   Docker runtime, and (recommended) `filesystem_policy=readonly`.

## Consequences

**Positive**
- The sandbox is now default-secure, fail-closed, enforcement-honest, boot-validated, and gives one
  workspace containment boundary for commands and agent file tools.
- Both Critical risks and all Pilot-gating risks are closed with verifiable, passing evidence.
- The genuinely-good prior properties (real Docker isolation, Docker fail-closed spawn, complete
  immutable audit) are preserved and extended with honesty metadata.

**Negative / accepted**
- R-04 (governance), R-08 (design-inherent), R-09 (default tightening) remain open/partial and must be
  closed before any Production Safe reclassification.
- Deliberate host execution (`provider=local`) is still permitted — by design, loudly warned and
  audited.
- In-container file I/O ceiling (R-05) is deferred defense-in-depth; the host-side workspace floor
  already prevents escape.

## Follow-ups (separately authorized, not part of this ADR)

- Documentation: apply the Sandbox row upgrade in `architecture-status-summary.md` + dependent docs.
- Governance AP: close R-04 (robust command policy).
- Track S enhancements: R-09 default `readonly`; in-container file I/O; R-08 argv/exec hardening.
- Commit Track S (S-2/S-3/S-4) to `v1.1.0-planning`.

## Verdict

> **APPROVED.** The execution sandbox is reclassified **Experimental → Pilot Safe**, conditioned as
> above, using only evidence currently present in the repository.
