# Branding Migration Report — Codename "Hermes" → Product "Nexus"

> **Milestone:** v1.1.0 "Containment" · Live Onboarding & Branding · **Status:** ✅ complete,
> validated, **uncommitted** (awaiting review). **Base:** clean (H-4 frozen at `c4c4f3c`, tag
> `hermes-pilot`). Authorized scope: **full rename — content + filenames** (operator decision).

---

## 1. Objective

Retire the internal development codename **"Hermes"** for the in-house autonomous agent runtime and
adopt the product name **"Nexus"** across code, runtime identifiers, and documentation — while
preserving routing/record compatibility and historical accuracy of external references.

## 2. Identifier mapping (code)

| Old (codename) | New (product) | Compatibility |
|---|---|---|
| registry id `"hermes"` | `"nexus"` (primary) | `get_adapter_cls` resolves `hermes` / `hermes_agent` → `nexus` (alias) |
| `class HermesRuntimeAdapter` | `class NexusRuntimeAdapter` | module-level `HermesRuntimeAdapter = NexusRuntimeAdapter` alias retained |
| `nexus/execution/runners/hermes.py` | `…/nexus_agent.py` | `git mv` (history preserved) |
| `nexus/execution/runners/hermes_tools.py` | `…/nexus_agent_tools.py` | `git mv` |
| `runtime="hermes"` (record write) | `runtime="nexus"` | legacy `runner="hermes"` rows still resolve via alias |
| `RunnerType.HERMES_AGENT` | `RunnerType.NEXUS_AGENT` (added) | `HERMES_AGENT` kept (deprecated) |
| `ALLOWED_RUNTIMES=[…,"hermes"]` | `[…,"nexus","hermes"]` | `hermes` retained for back-compat |
| `test_hermes*.py` (3) | `test_nexus_agent*.py` | `git mv` + import/reference updates |

**Collateral code/test files updated:** `runners/__init__.py`, `core/types.py`,
`core/policy_defaults.py`, `config.py` (comment), `scheduling/orchestrator.py` (comment),
`test_workspace_confinement.py`, `test_timeout_resolution.py`, `test_policy_externalization.py`
(`ALLOWED_RUNTIMES` assertion). **+1 regression test** added:
`test_registry_resolves_nexus_and_hermes_alias`.

## 3. Documentation rename

- **236** markdown files scanned; **139** had codename content rewritten; **26** files renamed
  (`*hermes*` → `*nexus*`, case-aware), including 4 ADRs, the `docs/07_HERMES_AGENT.md` design doc,
  and v1.0.1/v1.1.0 implementation reports. Cross-references were rewritten in lock-step so links
  remain valid.
- Performed via an auditable masking-based script (dry-run reviewed before apply); script removed
  after use (not committed).

## 4. Explicitly preserved (historical / external accuracy)

- **External project references** — `Nous Hermes`, `nousresearch/hermes-agent`, and that repository
  URL — left intact (incl. `blueprint/references/hermes-evaluation.md`, which evaluates the external
  project and was **excluded** from both rename and content rewrite).
- **Pushed git tags** `hermes-experimental` / `hermes-pilot` and their in-doc references — preserved
  (immutable refs; renaming would falsify the record).
- **Git history / commit messages / SHAs / dates / test counts** — untouched.

**Verification:** a post-apply scan for `Hermes`/`hermes` excluding the protected/external set
returned **zero** unprotected occurrences.

## 5. Known naming divergence (flagged)

Renaming dated ADR/report **filenames** to `nexus-*` while the already-pushed tags remain
`hermes-experimental` / `hermes-pilot` creates an intentional, documented name divergence between
the (now `nexus-*`) documents and the (still `hermes-*`) tags. The tags were **not** altered
(rewriting pushed refs is destructive and was not authorized). This is recorded here as the bridge.

## 6. Validation

| Gate | Result |
|---|---|
| pytest | **219 passed** (214 pre-onboarding + 5 onboarding) |
| ruff | All checks passed |
| mypy (`nexus/ --ignore-missing-imports`) | Success, 61 source files |

Zero regressions. The only test break during migration was an expected `ALLOWED_RUNTIMES`
assertion, root-caused and corrected.

## 7. Change-set totals (uncommitted)

31 renames (5 code/test + 26 docs) · 153 modified (≈9 code/test, remainder docs) · 2 new
(`nexus/onboarding.py`, `tests/unit/test_onboarding.py`).
