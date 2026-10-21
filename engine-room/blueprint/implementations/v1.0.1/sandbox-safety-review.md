# Sandbox Safety Review (A-006)

> Evidence-based security and containment audit of Nexus execution sandboxing. **Audit only** — no
> implementation, no source change, no refactor, no fixes. Objective: establish the exact containment
> reality. Every claim cites source.
>
> **Release:** v1.0.1 "Alignment" · **Finding:** A-006 · **Subject:** `nexus/execution/sandbox/` +
> `SandboxConfig` + runtime call-sites. Companion artifacts: `sandbox-capability-ledger.md`,
> `sandbox-execution-path-analysis.md`, `sandbox-risk-register.md`, `sandbox-boundary-analysis.md`,
> `ADR-sandbox-safety-review.md`.

---

## 1. The exact containment reality (one paragraph)

Nexus ships with sandboxing **disabled by default** (`SandboxConfig.enabled = False`, `config.py:135`).
Under that default, every governed command — for **all** runtimes (Gemini, Claude, Nexus
`execute_command`) — is routed by `SandboxManager` to the `LocalSandboxProvider`, which runs the full
command string in the **host shell** with full host privileges, no resource caps, full network, and full
filesystem access (`manager.py:44-45`, `provider.py:96`). The resource/network/filesystem policy is
computed and audited but **ignored** by the Local provider. A real containment boundary exists **only**
when an operator sets `enabled=True` **and** `provider="docker"` **and** Docker is present
(`provider.py:133-175`). Provider **resolution fails open**: any unknown/misspelled provider name falls
back to host execution (`manager.py:52-53`). The only barriers in the default posture are the human
approval gate, a repository allow-list, a bypassable 4-pattern substring command blacklist
(`governance.py:616-641`, `policy_defaults.py:9`), and complete after-the-fact audit logging.

## 2. The onboarding concerns — confirmed

| Concern (onboarding) | Verdict | Evidence |
|---|---|---|
| Default sandbox may execute on host | **Confirmed** | `config.py:135` `enabled=False` → `manager.py:44-45` Local → `provider.py:96` host shell |
| Unknown provider may fall back to host | **Confirmed** | `manager.py:52-53` `else: LocalSandboxProvider()` |
| Container isolation not enforced by default | **Confirmed** | Isolation lives only in Docker provider; default never reaches it; policy decorative under Local (`provider.py:88-101`) |

## 3. Required questions — answered (full detail in `sandbox-execution-path-analysis.md` §5)

1. **Default execution path:** host shell (`create_subprocess_shell`), no isolation.
2. **When host execution occurs:** disabled (default), non-`NexusSettings`, no sandbox config,
   `provider="local"`, or **any unknown provider name**.
3. **Unknown provider → host?** **Yes** — fail-open `else` branch.
4. **Docker failure fail closed/open?** **Closed at the manager** (raises, no host fallback,
   `manager.py:172-179`); but no Docker-availability precheck. The fail-**open** is in resolution/default.
5. **Sandboxing enabled by default?** **No.**
6. **Which runtimes pass through the sandbox?** All three command paths call `SandboxManager`; under
   default all land on host. Nexus file tools bypass the manager.
7. **Can any runtime bypass containment?** **Yes** — default Local path for all; Nexus `read/write_file`
   bypass outright.
8. **Protections against arbitrary host execution:** approval gate, allow-list + branch policy,
   substring blacklist, health gate, audit log (detection).
9. **Protections missing:** default isolation, policy enforcement under Local, fail-closed unknown
   provider, Docker/sandbox startup validation, robust command policy, agent path confinement.
10. **Real security classification:** **Unsafe By Default** (§6).

## 4. Capability classification (summary; full in ledger)

- **Production Ready:** audit logging.
- **Implemented:** provider ABC, Local/Docker/Mock providers, Docker fail-closed, container lifecycle,
  orphan cleanup, resource collector.
- **Partially Implemented:** provider resolution, CPU/mem/network/FS enforcement, command blacklist
  *(Docker-only / conditional; inert under default)*.
- **Not Present:** default isolation, fail-closed-on-unknown-provider, Docker availability validation,
  sandbox startup validation, agent file-path confinement.

## 5. Risk posture (summary; full in risk register)

🔴 Critical: default host execution (R-01), unknown-provider fail-open (R-02). 🔴 High: decorative
policy under Local (R-03), bypassable blacklist (R-04), agent file-tool bypass (R-05). 🟠 Medium: no
Docker validation (R-06), no startup validation (R-07), shell surface (R-08).

## 6. Final verdict — **Unsafe By Default**

**Evidence-supported verdict: Unsafe By Default.**

- Not **Unsafe** (absolute): a genuine, correct containment path exists (Docker provider enforces
  cpu/memory/network/filesystem), Docker failures fail **closed**, and all execution is fully audited.
  Properly configured (`enabled=True`, `provider=docker`, Docker present, ideally
  `filesystem_policy=readonly`), residual risk is Medium/Low.
- Not **Experimental/Pilot Safe/Production Safe**: the **shipped default executes arbitrary approved
  commands directly on the host** with decorative policy, provider misconfiguration **fails open** to the
  host, the command guard is a bypassable substring blacklist, and agent file tools bypass containment
  entirely. None of these are safe-by-default properties.

The system is **safe only when deliberately configured for isolation**; out of the box it relies on human
approval and a weak blacklist to stand between an approved command and the host. Hence **Unsafe By
Default**.

## 7. Operational guidance (until a future, separately-authorized hardening AP)

- Treat any default-config deployment as **host-executing**; run only fully-trusted commands/repos.
- For isolation, set `sandbox.enabled=true`, `sandbox.provider=docker`, ensure Docker is installed, and
  prefer `filesystem_policy=readonly`; verify a `sandbox.created` audit row shows the Docker policy.
- Note ADR-011 (local-first) tension: the documented Docker image lacks runtime CLIs (onboarding 09) —
  isolation and runtime availability are not yet jointly validated.

## 8. Boundary note

A-006 proposes **no fixes** and **no redesign**. "Missing protections" are stated descriptively;
remediation is future-Action-Point territory. The shared item with AP-105 (Nexus file-tool bypass /
R-05) is recorded in both audits. Authoritative status: `architecture-status-summary.md` already
classifies Sandbox Isolation **Experimental (default-off)** — this audit confirms and pins it.
