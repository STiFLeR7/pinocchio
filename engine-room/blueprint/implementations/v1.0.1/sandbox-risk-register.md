# Sandbox Risk Register (A-006)

> Evidence-based risk register for execution containment. Each risk: **Likelihood · Impact · Severity ·
> Mitigation Status · Evidence.** Audit-only — no remediation proposed.
>
> Likelihood: Certain / High / Medium / Low. Impact: Critical / High / Medium / Low.
> Severity = composite. Mitigation Status: None / Weak / Partial / Adequate.

---

## R-01 — Default configuration executes on the host with zero isolation
- **Likelihood:** Certain (it is the shipped default)
- **Impact:** Critical
- **Severity:** 🔴 Critical
- **Mitigation Status:** Weak — only the approval gate + bypassable blacklist stand between an approved
  command and the host
- **Evidence:** `config.py:135` `enabled=False`; `manager.py:44-45` → Local; `provider.py:96`
  `create_subprocess_shell(command, cwd=cwd)`

## R-02 — Unknown/misspelled provider name fails open to host
- **Likelihood:** Medium (config typo, env drift, partial setup)
- **Impact:** Critical (operator believes they are isolated; they are not)
- **Severity:** 🔴 Critical
- **Mitigation Status:** None
- **Evidence:** `manager.py:52-53` `else: return LocalSandboxProvider()`

## R-03 — Containment policy is decorative under the Local provider
- **Likelihood:** Certain whenever Local is active (i.e., by default)
- **Impact:** High (cpu/memory/network/filesystem limits silently unenforced)
- **Severity:** 🔴 High
- **Mitigation Status:** None — policy is built and audited, then ignored by Local
- **Evidence:** `manager.py:91-110` builds/audits `SandboxPolicy`; `provider.py:88-101` Local ignores it

## R-04 — Command blacklist is a bypassable substring match
- **Likelihood:** High (trivial to evade)
- **Impact:** Critical (arbitrary host command if isolation off)
- **Severity:** 🔴 High
- **Mitigation Status:** Weak — 4 fixed patterns, substring `in` check
- **Evidence:** `governance.py:616-641` `if pattern in command`; `policy_defaults.py:9`
  `["rm -rf /", "sudo ", "mv /etc", ":(){ :|:& };:"]` (e.g. `rm -rf /home`, `rm -rf  /`, `bash -c …`
  evade it)

## R-05 — Agent file tools bypass the sandbox entirely
- **Likelihood:** High (whenever Nexus runs)
- **Impact:** High (arbitrary host file read/write regardless of provider)
- **Severity:** 🔴 High
- **Mitigation Status:** None
- **Evidence:** `nexus.py:88-105` raw `open()/read()/write()` with no manager, no path confinement

## R-06 — No Docker availability validation
- **Likelihood:** Medium (Docker absent/daemon down on target host — note ADR-011 local-first)
- **Impact:** Medium (runs fail at spawn; but **fails closed**, no host fallback)
- **Severity:** 🟠 Medium
- **Mitigation Status:** Partial — fail-closed on spawn error (`manager.py:172-179`) limits impact, but
  no precheck/clear signal
- **Evidence:** `manager.py:48-49` returns Docker provider unconditionally; no availability probe

## R-07 — No sandbox startup/config validation (no fail-fast on unsafe config)
- **Likelihood:** Certain (no such check exists)
- **Impact:** Medium (an unsafe sandbox config boots silently; contrast A-001 owner-gate)
- **Severity:** 🟠 Medium
- **Mitigation Status:** None
- **Evidence:** `api.py` lifespan validates only owner IDs; no sandbox assertion anywhere

## R-08 — Shell-string execution surface (Local) / `sh -c` (Docker)
- **Likelihood:** Medium (by design runs approved arbitrary commands)
- **Impact:** High under Local (host); Low–Medium under Docker (contained)
- **Severity:** 🟠 Medium (design-inherent)
- **Mitigation Status:** Partial — approval + blacklist + (if enabled) container
- **Evidence:** `provider.py:96` `create_subprocess_shell`; `provider.py:165` `sh -c "<command>"`

## R-09 — `cwd` mounts the real repository path into the container (when Docker on)
- **Likelihood:** Medium
- **Impact:** Medium (writes to mounted workspace are real host writes unless `:ro`)
- **Severity:** 🟡 Low–Medium
- **Mitigation Status:** Partial — `filesystem_policy="readonly"` supported but default is `"restricted"`
  (not read-only)
- **Evidence:** `provider.py:154-159`; `config.py:140` `filesystem_policy="restricted"`

---

## Risk summary

| Severity | Risks |
|---|---|
| 🔴 Critical | R-01 default host exec, R-02 unknown-provider fail-open |
| 🔴 High | R-03 decorative policy, R-04 bypassable blacklist, R-05 agent file bypass |
| 🟠 Medium | R-06 no docker validation, R-07 no startup validation, R-08 shell surface |
| 🟡 Low–Med | R-09 workspace mount |

**Net:** containment is **opt-in**. With the default config, the residual risk of arbitrary host
execution/file-access is **Critical**, mitigated only by human approval, an allow-list, a weak
blacklist, and (valuably) complete after-the-fact audit. Properly configured (`enabled=True`,
`provider=docker`, Docker present, ideally `filesystem_policy=readonly`), residual risk drops to
Medium/Low. *No mitigation work is proposed by A-006.*
