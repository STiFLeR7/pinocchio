# A-006 — Sandbox Safety Review Report

> **Release:** Nexus v1.0.1 "Alignment" · **Finding:** A-006 (Sandbox Safety Review)
> **Type:** Evidence-based security/containment audit · **Status:** ✅ Complete
> **Constraints honored:** audit only — no implementation, no source change, no refactor, no feature work.

---

## 1. Mission

Establish the exact execution-containment reality of Nexus: default behavior, provider selection,
fallback paths, runtime integration, failure handling, and audit — and assign an evidence-supported
security classification. Not to fix or redesign containment.

## 2. Investigation performed (all required targets)

| Target | Read first-hand | Location |
|---|---|---|
| Sandbox manager | ✅ | `sandbox/manager.py` (full) |
| Provider selection / resolution / default | ✅ | `manager.py:34-53` |
| Provider implementations (Local/Docker/Mock) | ✅ | `sandbox/provider.py` (full) |
| Default provider | ✅ | `config.py:133-141` (`enabled=False`, `provider="local"`) |
| Docker provider | ✅ | `provider.py:127-207` |
| Fallback paths | ✅ | `manager.py:37-53` (fail-open to Local) |
| Runtime integrations | ✅ | Gemini `gemini.py:107`, Claude `claude.py:102`, Nexus `nexus.py:117` |
| Gemini/Claude/Nexus execution paths | ✅ | all route through `SandboxManager.execute` |
| Startup / configuration validation | ✅ | none found in `api.py` / `config.py` |
| Error handling / provider failures | ✅ | `manager.py:119-179` (fail-closed on spawn error) |
| Container lifecycle | ✅ | `provider.py:177-207`, `lifecycle.py:cleanup_orphaned_sandboxes` |
| Audit logging | ✅ | `sandbox/audit.py`, `manager.py:101-179` |
| Command guard | ✅ | `governance.py:616-641`, `policy_defaults.py:9` |

## 3. Deliverables (all required)

| Deliverable | Location | Done |
|---|---|---|
| `sandbox-safety-review.md` | `blueprint/implementations/v1.0.1/` | ✅ |
| `sandbox-capability-ledger.md` | `blueprint/implementations/v1.0.1/` | ✅ |
| `sandbox-execution-path-analysis.md` | `blueprint/implementations/v1.0.1/` | ✅ |
| `sandbox-risk-register.md` | `blueprint/implementations/v1.0.1/` | ✅ |
| `sandbox-boundary-analysis.md` | `blueprint/implementations/v1.0.1/` | ✅ |
| `ADR-sandbox-safety-review.md` | `blueprint/DECISIONS/` | ✅ |
| `A-006-report.md` | this file | ✅ |

## 4. Findings summary

**Onboarding concerns — all confirmed:** default host execution; unknown-provider fail-open; isolation
not enforced by default (`sandbox-safety-review.md` §2).

**Containment reality:** sandboxing is **opt-in**. Default (`enabled=False`) → `LocalSandboxProvider` →
host shell for all runtimes; policy is decorative under Local; real isolation exists **only** via the
Docker provider when explicitly enabled and available. Provider resolution **fails open** on unknown
names; Docker **spawn failures fail closed** (no host fallback). Audit logging is complete and immutable.

**Capability classification:** Production-Ready (audit); Implemented (providers, fail-closed-on-docker,
lifecycle, cleanup); Partially Implemented (resolution, cpu/mem/network/fs limits, blacklist — Docker-only/
conditional); Not Present (default isolation, fail-closed unknown provider, docker/startup validation,
agent path confinement). Full table in `sandbox-capability-ledger.md`.

**Risk:** 🔴 Critical R-01 (default host exec), R-02 (unknown-provider fail-open); 🔴 High R-03/R-04/R-05;
🟠 Medium R-06/R-07/R-08. Full register in `sandbox-risk-register.md`.

## 5. Final verdict

**Unsafe By Default.** A correct containment path exists (Docker enforces cpu/mem/network/fs; Docker
failures fail closed; full audit), but the **shipped default executes arbitrary approved commands on the
host** with decorative policy, provider misconfiguration **fails open**, the command guard is a bypassable
substring blacklist, and agent file tools bypass containment. Safe only when deliberately configured for
isolation. Recorded in `ADR-sandbox-safety-review.md` (Accepted).

## 6. Architecture boundary upheld

No implementation, redesign, or fix was proposed for execution. "Missing protections" are descriptive
gap statements; remediation sequencing is future-AP territory. **No source files were modified** — the
only changes are new `.md` deliverables.

## 7. Cross-finding linkage

- Status truth (A-004): `architecture-status-summary.md` classifies Sandbox Isolation **Experimental
  (default-off)** — this audit confirms and pins it; no doc rewrite needed.
- Nexus (A-005): R-05 (agent file-tool bypass, `nexus.py:88-105`) is the shared item with AP-105 Gap 7.
- ADR-011 (local-first): tension noted — Docker image reportedly lacks runtime CLIs, so isolation and
  runtime availability are not yet jointly validated.

## 8. Verdict

**Complete.** Execution-containment reality is fully established and evidence-pinned. With A-006 done,
**all six accepted v1.0.1 findings (A-001…A-006) are now addressed** (A-001/A-002/A-003 implemented;
A-004 documentation aligned; A-005/A-006 audited). The v1.0.1 "Alignment" finding set is complete; the
outstanding `v1.0.1-alignment-summary.md` release wrap-up remains per the original release deliverables.
