# Architecture Status Update — Sandbox Row (Track S)

> The exact, auditable set of status-document edits made during Track S closure. Scope was strictly
> limited to **Sandbox maturity references**; no other subsystem row was touched. Documentation-only.

---

## 1. Documents updated

| Document | Edit | Rationale |
|---|---|---|
| `blueprint/implementations/v1.0.1/architecture-status-summary.md` | Sandbox row Experimental → **Pilot Safe** (+ evidence, residuals); added Track S provenance header; added **Pilot Safe** to classification scale; updated rollup counts, one-line truth, watched-subsystem note | Canonical source of truth for subsystem status; all other docs must agree with it |
| `blueprint/STATUS.md` | Sandbox row → **Pilot Safe**; legend gains 🟢 Pilot Safe | Living status doc; mirrors canonical |
| `blueprint/ROADMAP.md` | A-006 → ✅ Complete; added Track S → **Pilot Safe** row | Roadmap referenced the (now-complete) sandbox safety review + maturity |
| `README.md` | Sandbox status row → **Pilot Safe**; **Sandboxing** section rewritten to the default-secure model | Public-facing status + sandbox guidance referenced the old default-host posture |

## 2. Canonical row — before vs after

**Before**
```
| Sandbox Isolation | 🟠 Experimental (default-off) | config.py:133-137 (provider="local") |
  Default = no isolation; host execution guarded only by substring blacklist. Review is A-006. |
```

**After**
```
| Sandbox Isolation | 🟢 Pilot Safe (Track S) | manager.py, provider.py, confinement.py, nexus.py,
  api.py; 35 sandbox tests | v1.1.0 Track S (S-2/S-3/S-4), effective on commit. Default-secure
  fail-closed (R-01/R-02), boot-validated + Docker probe (R-06/R-07), honest enforcement (R-03),
  workspace-confined file tools (R-05). Isolation opt-in. Residual R-04/R-08/R-09.
  Basis: ADR-sandbox-pilot-safe, track-s-closure-review.md. |
```

## 3. Rollup delta (architecture-status-summary.md)

| Band | Before | After |
|---|---|---|
| Production Ready | 5 | 5 |
| Operational | 5 | 5 |
| **Pilot Safe** | — | **1 (Sandbox)** |
| Stubbed | 2 | 2 |
| Mocked | 1 | 1 |
| Experimental | (listed 4; actually Sandbox + Health + Alembic) | **2 (Health, Alembic)** |
| Future | 3 | 3 |

> Note: the prior rollup line read "Experimental (4)" while listing three subsystems (Sandbox, Health,
> Alembic); removing Sandbox makes the corrected count **2** and the list self-consistent.

## 4. Consistency check (all docs now agree)

| Claim | architecture-status-summary | STATUS.md | ROADMAP.md | README.md |
|---|---|---|---|---|
| Sandbox = Pilot Safe | ✅ | ✅ | ✅ | ✅ |
| Default-secure / fail-closed | ✅ | ✅ | (implied) | ✅ |
| Isolation opt-in (docker) | ✅ | ✅ | — | ✅ |
| Residual R-04/R-08/R-09 disclosed | ✅ | ✅ | — | ✅ |
| Effective on commit (Track S uncommitted) | ✅ | ✅ | ✅ | (provenance via ADR) |

## 5. Deliberately NOT changed

- No other subsystem rows (Nexus still 🔴 Mocked; Gemini/Claude 🟠 Stubbed; Health/Alembic
  Experimental) — Track S touched only the sandbox.
- No runtime/behavior/test/config files.
- The v1.0.1 release framing of STATUS.md/ROADMAP.md (release line, AP history) — only the
  sandbox-maturity references within them were updated.
- `architecture-status-summary.md` retains its v1.0.0/v1.0.1 basis; the Track S change is an annotated,
  dated addendum, not a rewrite of the document's basis.

## 6. Effective condition

All edits describe a state that becomes **effective on commit** of Track S (code + docs) to
`v1.1.0-planning`. Each edited location carries that condition explicitly so a reader before the freeze
commit is not misled.
