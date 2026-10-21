# Documentation Alignment Report (AP-104)

> Records the corrections **actually applied** to project documentation in AP-104, with before→after
> and evidence. Companion to `documentation-drift-analysis.md` (which diagnosed the drift). Scope:
> **documentation only** — no source, config, migration, runtime, scheduler, or feature changes.
>
> **Release:** v1.0.1 "Alignment" · **Finding:** A-004 · **Basis:** accepted onboarding audit +
> first-hand repository inspection (`repository-state-map.md`).

---

## 1. Documents corrected

| Document | Before | After | Severity closed |
|---|---|---|---|
| `README.md` | pre-alpha, v0.1.0, Python 3.11+, all 8 phases "Pending", setup "when Phase 0 complete" | Released v1.0.0 + v1.0.1 line, Python 3.12+, truthful capability/runtime/governance/scheduler/sandbox sections, real quick-start, ADR/blueprint links | 🔴 → resolved |
| `blueprint/STATUS.md` | "Phase 1 Completed / next Phase 2", v0.1, 23 tests, phases 2–7 Not Started | v1.0.0 + v1.0.1 reality, per-subsystem classification, 143 tests, v1.0.1 AP progress, residual-debt notes | 🔴 → resolved |
| `blueprint/ROADMAP.md` | phases 2–7 "Not Started"; v0.1/v0.5/v1.0 future | Reconstructed delivered history (Phase 0–3,8 ✅ → v1.0.0 ✅ → v1.0.1 🔄), genuine Future section | 🟠 → resolved |
| `CHANGELOG.md` | only `[Unreleased]` scaffolding + `[0.0.1]` | added `[1.0.1] Unreleased` and `[1.0.0]` reconstructed from git + AP reports | 🟠 → resolved |
| `blueprint/README.md` | ADR list = 3; thin structure tree | 21-ADR pointer; full structure (onboarding/implementations/architecture/reports/action-points) | 🟡 → resolved |

## 2. New authoritative artifacts created

| Artifact | Role |
|---|---|
| `repository-state-map.md` | Ground-truth snapshot of what exists on disk |
| `documentation-drift-analysis.md` | Per-document drift (claims vs reality, severity, evidence) |
| `architecture-status-summary.md` | **Single source of truth** for per-subsystem status |
| `release-history-reconstruction.md` | True project history (Goals/Achievements/Lessons/Deferred) from git |
| `documentation-alignment-report.md` | This report — corrections applied |
| `AP-104-report.md` | AP closure report |
| `NEXUS_DOCUMENTATION_ALIGNMENT_SUMMARY.md` (root) | Executive summary + accuracy score |

## 3. What was deliberately **not** changed (scope discipline)

- **No source/config edits.** The in-code version string (`__init__.py`/`pyproject` `0.1.0`),
  `/api/v1/status` `"stub"` output, runtime behavior, and `requires-python` were left untouched; the
  version mismatch is logged as residual debt, not silently "fixed" by editing code.
- **Design docs left intact.** The numbered `docs/` remain valid design-intent; rather than rewriting
  them, the README "Documentation" table now flags them as design-intent and points readers to
  `architecture-status-summary.md` for current status. (Prevents creating *new* drift by editing
  forward-looking specs.)
- **No subsystem over-claiming.** Nexus is documented as **Mocked (partial)** and Gemini/Claude as
  **Stubbed** everywhere — never as functional integrations. The full Nexus ledger remains AP-105.
- **Sandbox** described honestly as default-no-isolation; the configuration audit remains A-006.

## 4. Consistency guarantee

All status statements across `README.md`, `blueprint/STATUS.md`, and `blueprint/ROADMAP.md` are
derived from the same table in `architecture-status-summary.md`. If they ever diverge, that file wins.

## 5. Evidence trail

Every "After" claim is traceable: README/STATUS/ROADMAP statuses ← `architecture-status-summary.md`
← first-hand source inspection (`repository-state-map.md` §2–§4) cross-checked with the accepted
onboarding audit (`blueprint/onboarding/09`, `NEXUS_FIRST_IMPRESSION.md`) and git history
(`release-history-reconstruction.md` §timeline).
