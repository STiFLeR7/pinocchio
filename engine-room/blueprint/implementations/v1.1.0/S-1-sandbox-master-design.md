# S-1 — Sandbox Master Design (v1.1.0 "Containment")

> **Track S · Design only — no implementation, no code, no runtime change, no migration.** Integrating
> design for moving the execution sandbox **Unsafe By Default → Safe By Default → Pilot Safe**. Every
> proposal traces to accepted v1.0.1 evidence (A-006: `sandbox-safety-review.md`,
> `sandbox-capability-ledger.md`, `sandbox-risk-register.md`, `sandbox-execution-path-analysis.md`,
> `sandbox-boundary-analysis.md`; `ADR-sandbox-safety-review.md`).
>
> Branch `v1.1.0-planning`, off frozen `v1.0.1` (`ab5937b`). v1.0.1 is immutable history.

---

## 1. Mission & target

Make isolation the **default and guaranteed** property, and make every unsafe path a **deliberate,
audited, fail-closed** exception — without redesigning governance, approval, runtime abstraction,
scheduler, memory, or events (Architecture Rules 1–10). Target verdict: **Pilot Safe**
(`ADR-sandbox-safety-review.md` defines the bar).

## 2. Starting evidence (what A-006 proved, verbatim sources)

| Defect | Evidence | Risk |
|---|---|---|
| Default = host execution (no isolation) | `config.py:135` `enabled=False` → `manager.py:44-45` Local → `provider.py:96` host shell | R-01 (Critical) |
| Fail-open provider resolution | `manager.py:52-53` `else: LocalSandboxProvider()` | R-02 (Critical) |
| Decorative policy under Local | `manager.py:91-110` builds/audits policy; `provider.py:88-101` Local ignores it | R-03 (High) |
| Nexus file-tool host bypass | `nexus.py:88-105` | R-05 (High, **shared**) |
| No startup/Docker validation | none in `api.py` lifespan; no Docker probe | R-06/R-07 |

What is **already good** and must be preserved: the Docker provider correctly enforces
cpu/mem/network/fs (`provider.py:133-175`); Docker spawn failure **fails closed** (`manager.py:172-179`);
audit logging is complete and immutable (`audit.py`, `manager.py:101-179`).

## 3. The five sub-designs (this track)

| Doc | Concern | Answers |
|---|---|---|
| `S-1-sandbox-boundary-model.md` | Trust zones, the to-be boundary | Q1, Q5 |
| `S-1-provider-resolution-design.md` | Fail-closed resolution + availability | Q2, Q4 |
| `S-1-security-policy-design.md` | Policy enforced-or-fail-closed; startup validation | Q2, Q3, Q5 |
| `S-1-runtime-containment-design.md` | Per-runtime containment incl. file tools | Q5, Q6 |
| `../v1.1.0/R-05-shared-resolution.md` | Nexus file-tool confinement (shared) | Q6 |

## 4. Required questions — master answers (detail in sub-designs)

1. **Default execution path?** **Isolation-required.** The default must never be unrestricted host
   execution. If Docker is available → use it; if not available → **fail closed** (refuse governed
   command execution) unless the operator *explicitly and loudly* opts into an acknowledged unsafe host
   mode. (→ boundary-model, provider-resolution.)
2. **What must fail closed?** Unknown/misspelled provider; missing Docker when isolation is required;
   incoherent/unsafe sandbox config at startup; any policy the selected provider cannot enforce. (→
   provider-resolution, security-policy.)
3. **Startup validations?** A lifespan sandbox-config gate (mirroring the A-001 owner gate,
   `api.py:67-82`): probe Docker when required; abort on unknown provider; emit a loud audit + warning
   for any explicit host-unsafe mode. (→ security-policy.)
4. **Provider resolution?** Explicit known-provider map; **unknown → raise** (remove the
   `else→Local` fail-open); availability-checked; validated at startup **and** execute-time. (→
   provider-resolution.)
5. **Runtime containment enforcement?** Containment = the Docker boundary; the `SandboxPolicy` is
   **honored or the run fails closed** (no decorative pass); Local is reclassified as *explicitly unsafe,
   opt-in only*. (→ runtime-containment, security-policy.)
6. **Nexus file tools participation?** File tools route through the same containment/path-confinement
   boundary; owned by Track S, consumed by Track H — single resolution in `R-05-shared-resolution.md`.
7. **Pilot Safe constitutes:** default-secure; fail-closed resolution; startup validation; enforced
   policy (or fail closed); file tools confined; audit complete (already true).
8. **Intentionally deferred:** full Production-Safe hardening (seccomp/AppArmor, rootless, image
   signing); non-Docker backends (gVisor/Firejail); OS-level "genuinely restricted local mode"; network
   egress filtering beyond `--network none`. v1.1.0 targets **Pilot Safe** only.

## 5. Design principles

- **Safe by default, unsafe by explicit choice** — invert the current default; host execution becomes a
  deliberate, audited opt-in, never a silent fallback.
- **Fail closed, never fail open** — every ambiguity (unknown provider, missing Docker, unenforceable
  policy) refuses rather than degrades to host.
- **Reuse the chokepoint** — all containment changes happen behind the existing single
  `SandboxManager.execute` seam that all runtimes already use (Rule 9). No new execution paths.
- **Preserve the good** — Docker provider, fail-closed Docker errors, and the audit ledger are kept
  intact (Rules 4, 7).

## 6. Promotion gate (evidence-defined)

| Gate | Condition (evidence required) |
|---|---|
| **Unsafe By Default → Pilot Safe** | R-01, R-02, R-03, R-06, R-07 closed; R-05 closed (shared); audit unchanged; tests prove default-secure + fail-closed resolution + enforced-or-refused policy |

## 7. Out of scope (reject if proposed)

Everything in the v1.1.0 deferred list; any governance/approval redesign (the command-blacklist R-04 is
*adjacent*, governance-owned — see security-policy §note; treated as an optional, additive, bounded
item, **not** a governance redesign); non-Docker isolation backends; production-grade hardening.

## 8. Status

Design only. No code, no commit, no migration. Sub-designs + `ADR-sandbox-v1.1-foundation.md` accompany
this for review. Implementation APs remain **gated** until accepted.
