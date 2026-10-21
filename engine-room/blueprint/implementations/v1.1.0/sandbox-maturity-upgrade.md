# Sandbox Maturity Upgrade — Experimental → Pilot Safe

> The formal maturity-classification change record for the execution sandbox, with the evidence chain
> that authorizes it. Companion to `ADR-sandbox-pilot-safe.md`. Documentation-only.

---

## 1. Classification change

| | Before | After |
|---|---|---|
| Maturity (architecture-status-summary axis) | 🟠 Experimental (default-off) | 🟢 **Pilot Safe** |
| Security classification (A-006 axis) | **Unsafe By Default** | **Pilot Safe** |
| Default behavior | Silent host execution | **Fail-closed** (refuses implicit host run) |
| Authoritative ADR | `ADR-sandbox-safety-review` | `ADR-sandbox-pilot-safe` (supersedes classification only) |
| Effective | — | **On commit** of Track S to `v1.1.0-planning` |

## 2. The four reversed facts (why the upgrade is earned)

The "Unsafe By Default" label rested on four facts. Each is now reversed **in code with passing tests**:

| # | "Unsafe By Default" fact | Reversal | Risk(s) | Evidence |
|---|---|---|---|---|
| 1 | Default ran on host silently | Disabled/real config ⇒ `SandboxResolutionError` at construction | R-01 | `manager.py:50-55`; `test_disabled_sandbox_fails_closed` |
| 2 | Unknown provider fell open to host | Unrecognized provider ⇒ fail-closed (no fallback) | R-02 | `manager.py:57-64`; `test_unknown_provider_fails_closed` |
| 3 | Policy decorative; no startup validation | `policy_enforced` honesty + boot gate + Docker probe | R-03, R-06, R-07 | `provider.py:65,146,151-170`; `manager.py:121,196-256`; `api.py:106-113` |
| 4 | Agent file tools bypassed containment | Workspace-confined, fail-closed, provider-independent | R-05 | `confinement.py`; `nexus.py:96-117`; `test_nexus_*_escape_denied` |

## 3. Evidence chain (authoritative, accepted)

```
A-006 (sandbox-risk-register.md, ADR-sandbox-safety-review.md)   ← baseline: Unsafe By Default, R-01..R-09
        │
        ├── S-2  ▸ R-01, R-02 closed   (impl + validation, accepted)
        ├── S-3  ▸ R-03, R-06, R-07 closed   (impl + validation, accepted)
        └── S-4  ▸ R-05 closed   (impl + validation, accepted)
        │
track-s-closure-review.md  ▸ verdict APPROVED (re-verified live: 178 passed, ruff+mypy clean)
track-s-risk-matrix.md     ▸ 6 closed / 1 partial / 2 open (out of charter)
track-s-before-after.md    ▸ posture delta
        │
ADR-sandbox-pilot-safe.md  ▸ Accepted: Experimental → Pilot Safe
        │
THIS UPGRADE  ▸ propagated to architecture-status-summary.md, STATUS.md, ROADMAP.md, README.md
```

## 4. Why Pilot Safe and not Production Safe

Pilot Safe is the correct ceiling because three register items remain, all **out of the Track S
charter**:

- **R-04** (command blacklist robustness) — governance-owned; mitigated by approval gate + audit +
  (when on) container isolation.
- **R-08** (shell exec surface) — design-inherent to "run approved commands"; bounded under Docker.
- **R-09** (default mount not `readonly`) — `:ro` available; default tightening is an enhancement.

Host execution also remains *possible* by deliberate, warned, audited opt-in — appropriate for a
supervised pilot, not for an unconditional production isolation guarantee.

## 5. Conditions on the new classification

1. **Pilot Safe, not Production Safe** — disclose R-04/R-08/R-09 wherever cited.
2. **Effective on commit** — evidence-bound to the Track S source (uncommitted at time of writing).
3. **Production isolation** still requires `enabled=true` + `provider=docker` + Docker present
   (+ recommended `readonly`).

## 6. Maturity scale note

"Pilot Safe" is added to the `architecture-status-summary.md` classification scale as a
security-classification grade: *default-secure and fail-closed; safe for supervised pilot use with
documented residual risks.* It sits above Experimental and below Production Ready/Safe on the trust
axis.
