# ADR-sandbox-safety-review: Execution Sandbox Classified as Unsafe By Default

Date: 2026-06-24
Status: Accepted
Release: v1.0.1 "Alignment" · A-006 · Finding A-006 (Sandbox Safety Review)
Related: ADR-011-local-first-deployment, ADR-010-execution-timeouts, ADR-nexus-reality-audit,
`blueprint/implementations/v1.0.1/sandbox-safety-review.md`

---

## Context

The accepted onboarding audit flagged that the default sandbox may execute on the host, that unknown
provider names may fall back to host execution, and that container isolation may not be enforced by
default. A-006 was commissioned as an **evidence-based, audit-only** containment review (no
implementation) to establish the exact reality and a defensible security classification.

First-hand findings (full evidence in the A-006 deliverables):

- **Default is host execution.** `SandboxConfig.enabled = False` (`config.py:135`) routes all commands
  to `LocalSandboxProvider`, which runs them in the host shell (`manager.py:44-45`, `provider.py:96`).
- **All runtimes share the chokepoint.** Gemini (`gemini.py:107`), Claude (`claude.py:102`), and Nexus
  `execute_command` (`nexus.py:117`) all call `SandboxManager`; under default all run on host. Nexus
  `read_file`/`write_file` bypass the manager entirely (`nexus.py:88-105`).
- **Containment is opt-in and real only in Docker.** The Docker provider correctly enforces CPU,
  memory, network, and filesystem policy (`provider.py:133-175`); the Local provider **ignores** the
  policy (decorative).
- **Resolution fails open.** Unknown/misspelled provider names fall back to host (`manager.py:52-53`).
- **Docker failures fail closed** at the manager (raise, no host fallback, `manager.py:172-179`), but
  there is no Docker-availability or sandbox startup validation.
- **Weak preventive guard.** The only command filter is a 4-pattern substring blacklist
  (`governance.py:616-641`, `policy_defaults.py:9`). Audit logging, by contrast, is complete and
  immutable (`audit.py`).

## Decision

**Classify the execution sandbox as "Unsafe By Default."**

- The sandbox **must not** be represented as providing isolation out of the box. Authoritative status
  remains **Experimental (default-off)** in `architecture-status-summary.md`.
- Isolation is an **opt-in** property requiring `sandbox.enabled=true`, `sandbox.provider=docker`, a
  present Docker runtime, and (recommended) `filesystem_policy=readonly`.
- This classification is **evidence-bound**: it changes only when code + evidence change the default
  posture — not on intent.
- A-006 authorizes **no implementation, fix, or redesign.** "Missing protections" in the deliverables
  are descriptive only.

## Consequences

**Positive**
- Containment reality is now explicit and evidence-pinned; status honesty (extending A-004) is preserved.
- A prioritized risk register (R-01 default host exec, R-02 unknown-provider fail-open as Critical)
  exists for a future, separately-authorized hardening AP.
- The genuinely-good properties (real Docker isolation, Docker fail-closed, complete audit) are recorded
  so they are preserved through any future change.

**Negative / accepted**
- The default-config deployment continues to execute approved commands on the host until a future code
  AP changes the default posture (logged, deliberately not fixed under A-006).
- "Multi-runtime execution" is safe only under deliberate isolation configuration.

**Operational guidance (until remediated)**
- Treat default deployments as host-executing; restrict to fully-trusted commands/repositories; rely on
  the approval gate and audit log as the primary controls.
- Enable Docker isolation for any untrusted workload; verify via the `sandbox.created` audit policy.
- Cross-reference ADR-nexus-reality-audit: Nexus file-tool bypass (R-05) is shared between A-005/A-006.
- Note ADR-011 tension: the Docker image reportedly lacks runtime CLIs — isolation + runtime
  availability are not yet jointly validated.
