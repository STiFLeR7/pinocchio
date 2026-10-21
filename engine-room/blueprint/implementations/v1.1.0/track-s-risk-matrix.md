# Track S Risk Matrix — A-006 R-01…R-09 Disposition

> Authoritative disposition of the full A-006 sandbox risk register after Track S (S-2/S-3/S-4).
> Evidence re-verified against current source (HEAD `2fd3ffc`) and a live test/lint/type run
> (178 passed · ruff clean · mypy clean). Source of original severities: `sandbox-risk-register.md`.

---

## 1. Full register disposition

| Risk | Description | Severity (A-006) | Closed by | Status | Primary evidence (source) | Test evidence |
|---|---|---|---|---|---|---|
| **R-01** | Default config executes on host, zero isolation | 🔴 Critical | S-2 | ✅ **CLOSED** | `manager.py:50-55` (disabled ⇒ raise) | `test_disabled_sandbox_fails_closed`, `test_default_production_settings_fail_closed` |
| **R-02** | Unknown/misspelled provider fails open to host | 🔴 Critical | S-2 | ✅ **CLOSED** | `manager.py:57-64` + `RECOGNIZED_PROVIDERS` (`provider.py:296-300`) | `test_unknown_provider_fails_closed`, `test_unknown_provider_cannot_execute` |
| **R-03** | Containment policy decorative under Local | 🔴 High | S-3 | ✅ **CLOSED** (honesty + boot gate) | `provider.py:65,146`; `manager.py:121` (`policy_enforced`) | `test_execute_audit_declares_policy_enforcement`, `test_*_enforce_policy_flag` |
| **R-04** | Command blacklist bypassable substring match | 🔴 High | — | ⛔ **OPEN** (out of Track S; governance-owned) | `governance.py:616-641`, `policy_defaults.py:9` | n/a (deferred to governance AP) |
| **R-05** | Agent file tools bypass sandbox | 🔴 High | S-4 | ✅ **CLOSED** (floor) | `confinement.py`; `nexus.py:96-117,75-80` | `test_nexus_read_escape_denied`, `test_nexus_write_escape_denied`, `test_parent_traversal_denied`, `test_deep_traversal_denied`, `test_confinement_independent_of_provider` |
| **R-06** | No Docker availability validation | 🟠 Medium | S-3 | ✅ **CLOSED** | `provider.py:151-170`; `manager.py:238-244` | `test_startup_docker_unavailable_aborts`, `test_docker_ensure_available_raises_when_missing`, `test_docker_ensure_available_raises_on_nonzero` |
| **R-07** | No sandbox startup/config validation | 🟠 Medium | S-3 | ✅ **CLOSED** | `manager.py:196-256`; `api.py:106-113` | `test_startup_unknown_provider_aborts`, `test_startup_docker_unavailable_aborts` |
| **R-08** | Shell-string exec surface (`create_subprocess_shell` / `sh -c`) | 🟠 Medium | — | ⛔ **OPEN** (design-inherent, bounded) | `provider.py:111` (Local), `provider.py:204` (Docker `sh -c`) | n/a (deferred; bounded by Docker isolation) |
| **R-09** | `cwd` mounts real repo; default `filesystem_policy` not readonly | 🟡 Low–Med | — | 🟨 **PARTIAL** | `provider.py:194-198` (`:ro` supported); `config.py:140` default `restricted` | n/a (enhancement: default ⇒ readonly) |

## 2. Counts

| Disposition | Risks | Count |
|---|---|---|
| ✅ Closed | R-01, R-02, R-03, R-05, R-06, R-07 | **6** |
| 🟨 Partial | R-09 | **1** |
| ⛔ Open | R-04, R-08 | **2** |

- **Critical risks (R-01, R-02): both CLOSED.**
- **Pilot-gating set (R-01, R-02, R-03, R-05, R-06, R-07): all CLOSED.**
- Open/partial items are all **out of the Track S charter** (governance / design-inherent / default
  tightening) and individually tracked for future APs.

## 3. Severity heatmap — before vs after Track S

| Severity band | Before (open) | After Track S (open/partial) |
|---|---|---|
| 🔴 Critical | R-01, R-02 | — (both closed) |
| 🔴 High | R-03, R-04, R-05 | R-04 (governance) |
| 🟠 Medium | R-06, R-07, R-08 | R-08 (design-inherent) |
| 🟡 Low–Med | R-09 | R-09 (partial) |

Net: the entire 🔴 Critical band and the High band's containment risks (R-03, R-05) are eliminated;
the surviving High (R-04) is a governance concern, not a sandbox-containment one.

## 4. Pilot Safe gate (from `ADR-sandbox-v1.1-foundation.md` / `S-1-sandbox-master-design.md`)

| Pilot Safe requirement | Closing risk(s) | Met? |
|---|---|---|
| No silent host execution by default | R-01 | ✅ |
| No fail-open on misconfiguration | R-02 | ✅ |
| Honest policy enforcement (no decorative claims) | R-03 | ✅ |
| Provider availability verified before execution | R-06 | ✅ |
| Fail-fast startup on unsafe/incoherent config | R-07 | ✅ |
| Single containment boundary incl. agent file tools | R-05 | ✅ |

**All six Pilot-gating requirements met with passing test evidence. No remaining Pilot blockers.**

## 5. Residual-risk acceptance statement (Pilot scope)

For a **supervised pilot**, the open/partial items are acceptable because:
- **R-04**: every command still passes the human approval gate and is fully audited; container
  isolation (when on) contains a blacklist evasion.
- **R-08**: contained under Docker (the path for untrusted workloads); Local shell surface only via a
  deliberate, startup-warned opt-in.
- **R-09**: writes are confined to the operator-approved workspace; `readonly` is available for
  stricter pilots.

These would need closure (R-04, R-08) / default-tightening (R-09) before any **Production Safe** claim.
