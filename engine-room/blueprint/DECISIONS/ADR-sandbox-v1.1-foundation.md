# ADR-sandbox-v1.1-foundation: Sandbox Hardening Design (Unsafe By Default → Safe By Default → Pilot Safe)

Date: 2026-06-24
Status: Proposed (design — implementation gated)
Release line: v1.1.0 "Containment" · Track S
Related: ADR-sandbox-safety-review (v1.0.1, Accepted), ADR-011-local-first-deployment,
ADR-v1.0.1-alignment-release, `S-1-sandbox-master-design.md` (+ boundary/provider/policy/containment
sub-designs), `R-05-shared-resolution.md`
Supersedes: none (builds on the accepted Unsafe-By-Default classification)

---

## Context

`ADR-sandbox-safety-review` (Accepted, v1.0.1) classified the execution sandbox **Unsafe By Default**:
the shipped default (`enabled=False`, `config.py:135`) routes all runtimes to the host shell
(`manager.py:44-45`, `provider.py:96`); provider resolution **fails open** on unknown names
(`manager.py:52-53`); the containment policy is **decorative** under the Local provider
(`provider.py:88-101`); Nexus file tools **bypass** the sandbox (`nexus.py:88-105`, R-05); and there is
**no startup validation** (R-07). The Docker provider, Docker-failure fail-closed behavior, and the
audit ledger are genuinely sound and must be preserved. v1.1.0 Track S evolves the sandbox to **Pilot
Safe** — design first, implementation separately gated — without redesigning governance, approval,
runtime abstraction, scheduler, memory, or events.

## Decision

Adopt the S-1 design, founded on two inversions and one preservation:

1. **Safe by default** — the default execution posture is **isolation-required**: Docker when available;
   when absent, **fail closed** for governed command execution. Host execution becomes an explicit,
   named, **loudly-audited** `host-unsafe` opt-in — never a silent default or fallback. (Closes R-01;
   reconciles ADR-011 local-first without a hidden host path.)
2. **Fail closed, never fail open** —
   - Unknown/misspelled provider ⇒ **raise** (remove `else→Local`). (R-02)
   - `provider=docker` ⇒ Docker availability probed; unavailable ⇒ fail closed. (R-06)
   - Policy unenforceable by the active provider ⇒ fail closed, or (host-unsafe) **declared unenforced**
     in audit — never pretended. (R-03)
   - **Startup gate** in the `api.py` lifespan (mirroring the accepted A-001 owner gate) aborts boot on
     unsafe/incoherent config and audits `host-unsafe` usage. (R-07)
3. **Preserve the good** — single `SandboxManager.execute` chokepoint, the Docker provider, Docker
   fail-closed semantics, and the complete immutable audit ledger are kept (Rules 1, 2, 4, 9).

**R-05 (shared):** Nexus file tools are brought under the boundary via **workspace path-confinement as
an always-on floor** (plus in-container semantics when Docker is active); Track S owns the seam, Track H
consumes it; single resolution in `R-05-shared-resolution.md`.

**Boundaries:** no governance/approval redesign — the command-blacklist (R-04) is adjacent and
governance-owned; isolation-by-default mitigates its *impact*, and any blacklist hardening is an
**optional, additive, separately-gated** sub-item, not a v1.1.0 commitment. No non-Docker backends, no
production-grade hardening (seccomp/AppArmor/rootless/egress filtering), no OS-level restricted-local
mode — all deferred.

## Consequences

**Positive**
- The default becomes safe; every unsafe path is deliberate, audited, and fail-closed.
- Hardening the single chokepoint protects all runtimes at once; file-tool confinement closes the last
  reach-around (R-05).
- Pure reuse of existing primitives (manager/provider contract, Docker provider, lifespan-validation
  pattern, audit ledger) — minimal surface, no hidden coupling.

**Negative / accepted**
- Local-first operators without Docker must **explicitly** opt into `host-unsafe` (a deliberate friction
  that makes risk visible) — accepted per ADR-011 reconciliation.
- R-04 (command guard) is not structurally fixed in v1.1.0; its impact is mitigated by containment, not
  eliminated.
- Until implementation lands, the sandbox remains Unsafe By Default; classification does not change on
  design alone.

**Implementation sequencing (gated, not authorized here)**
S-2 default-secure + fail-closed resolution (R-01/R-02) → S-3 enforced policy + Docker/startup validation
(R-03/R-06/R-07) → S-4 file-tool confinement (R-05, with Track H) [+ optional R-04 sub-item]. Each is a
separate, separately-approved AP. **Implementation order vs Track H:** the S containment seam (S-4 / R-05)
precedes Nexus file-tool adoption (H-5).

## Status

**Proposed.** Design artifacts complete and submitted for review. No code, no migration, no commit of
implementation. Awaiting acceptance before any S-2+ implementation AP begins.
