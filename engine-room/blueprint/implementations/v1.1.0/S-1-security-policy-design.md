# S-1 — Security Policy Design (v1.1.0)

> **Track S · Design only.** Makes the containment policy *enforced-or-fail-closed* (ending the
> decorative policy), and defines the startup validation gate. No code. Answers Q3 (startup validations)
> and Q5 (enforcement); notes the adjacent governance-owned command guard.

---

## 1. Problem (evidence)

- The `SandboxPolicy` (cpu/mem/network/fs) is built and audited in the manager (`manager.py:91-110`) but
  **ignored** by the Local provider (`provider.py:88-101`) — **R-03 (High), decorative policy**.
- There is **no startup validation** of sandbox config — an unsafe config boots silently (**R-07**).
- (Adjacent) the command guard is a bypassable 4-pattern substring blacklist in *governance*
  (`governance.py:616-641`, `policy_defaults.py:9`) — **R-04**, governance-owned.

## 2. Enforcement principle — "honored or refused"

A policy that cannot be enforced by the active provider must cause the run to **fail closed**, never to
silently proceed unprotected.

| Provider | Can enforce cpu/mem/network/fs? | Design rule |
|---|---|---|
| Docker | **Yes** (`provider.py:145-159`) | Enforce; this is the containment mechanism |
| Local (`host-unsafe`) | **No** (by nature) | Allowed only as explicit, acknowledged, loudly-audited host mode — and the policy is **declared unenforced** in the audit, not pretended |
| Mock | n/a | Test only; rejected in production config |

**Result:** the "decorative policy" disappears — either the policy is genuinely enforced (Docker) or the
unenforced state is an **explicit, audited operator choice** (host-unsafe), not a silent default
(closes R-03).

## 3. Filesystem policy default

- Today `filesystem_policy="restricted"` (`config.py:140`); the Docker provider maps `readonly` →
  `:ro` mount (`provider.py:157-159`).
- **Design preference:** default the workspace mount toward **least privilege** (read-only unless the run
  legitimately needs writes), with writes confined to the workspace. This underpins R-05 (file-tool
  confinement) and is detailed in `R-05-shared-resolution.md`.

## 4. Startup validation gate (Q3, R-07)

A sandbox config gate in the `api.py` lifespan, modeled on the accepted A-001 owner gate
(`_validate_startup_configuration`, `api.py:67-82`):

| Check | Outcome on failure |
|---|---|
| Provider name is known | abort boot (unknown ⇒ fail closed) |
| `provider=docker` ⇒ Docker reachable | abort boot (or refuse Docker selection) |
| `provider=mock` in a production environment | abort boot (no test provider in prod) |
| `provider=host-unsafe` selected | boot **allowed** but emit a loud `critical`/`warning` log + audit row |
| Policy coherent with provider | abort boot on incoherence (e.g. limits requested but unenforceable and not acknowledged) |

This makes unsafe configuration a **boot-time, fail-fast** event — consistent with how A-001 made
fail-open auth a boot-time refusal.

## 5. Adjacent: command guard (R-04) — bounded, optional, NOT a governance redesign

R-04 (bypassable substring blacklist) lives in **governance** (`governance.py:616-641`), governed by
**Architecture Rule 5 (preserve approval/governance model)**. Therefore:

- v1.1.0 Track S **does not redesign** the governance gate or the approval model.
- The *only* permissible, **additive** improvement is treating the command policy as data that could be
  strengthened (e.g. richer match semantics) **within the existing gate** — proposed as an **optional,
  lower-priority sub-item**, explicitly **candidate-defer** if it risks touching governance structure.
- Primary v1.1.0 containment safety comes from **isolation by default** (a contained `rm -rf /home`
  cannot harm the host), which mitigates R-04's *impact* without changing governance.

**Decision:** R-04 is documented as adjacent/known; the containment-first approach reduces its severity;
any blacklist hardening is optional, additive, and gated separately — not a v1.1.0 Track S commitment.

## 6. Architecture preservation

- Policy enforcement stays inside the `SandboxManager`/provider contract (Rule 1, 2).
- Startup gate reuses the lifespan-validation pattern (consistency; Rule 5 respected — governance gate
  itself untouched).
- All policy decisions/refusals/unsafe-mode usage are audited (Rule 4). No hidden coupling (Rule 9).

## 7. Closes / addresses

R-03 (decorative policy), R-07 (no startup validation); contributes to R-01 (default-secure); **notes**
R-04 as adjacent/bounded. Tier: **Pilot Safe**.
