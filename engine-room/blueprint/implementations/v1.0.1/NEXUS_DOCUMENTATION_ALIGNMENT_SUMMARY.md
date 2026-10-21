# NEXUS — Documentation Alignment Summary

> **AP-104 · v1.0.1 "Alignment" · Finding A-004.** Executive summary of the documentation-alignment
> pass that brought Nexus's project documentation back into agreement with the actual repository.
> Documentation only — no code, config, runtime, scheduler, or feature changes. Full detail lives in
> `blueprint/implementations/v1.0.1/`.

---

## What was inaccurate

The documentation described a project that **had barely started building**, while the repository is a
**released v1.0.0 system** undergoing a v1.0.1 safety pass:

- **README** advertised *pre-alpha, v0.1.0, Python 3.11+*, with **all 8 phases "Pending"** and "setup
  when Phase 0 is complete."
- **blueprint/STATUS** froze at *"Phase 1 complete, next is Phase 2," v0.1, 23 tests* — omitting
  approvals, execution, governance, runtimes, research, briefing, outbox, metrics, and the scheduler.
- **blueprint/ROADMAP** marked **Phases 2–7 "Not Started"** — the inverse of reality.
- **CHANGELOG** had **no v1.0.0 and no v1.0.1** entries at all.
- **blueprint landing page** listed **3 of 21 ADRs**.
- Older `docs/`/ADRs leaned on a **scheduler that did not exist at v1.0.0** (now built in v1.0.1).

## What was corrected

- **README.md** — rewritten to the released-v1.0.0 + v1.0.1 reality: honest capability matrix, runtime
  support (stubbed/mocked stated), governance/research/briefing/scheduler/sandbox sections, correct
  Python 3.12+, real quick-start, and links to ADRs + the authoritative status summary.
- **blueprint/STATUS.md** — replaced with a per-subsystem classification (Completed/Operational/
  Experimental/Stubbed/Mocked/Deferred/Future), 143-test reality, and v1.0.1 AP progress.
- **blueprint/ROADMAP.md** — reconstructed true history (Phases 0–3,8 ✅ → v1.0.0 ✅ → v1.0.1 🔄) with a
  genuinely-forward Future section.
- **CHANGELOG.md** — added reconstructed `[1.0.0]` and `[1.0.1] Unreleased` sections.
- **blueprint/README.md** — corrected the ADR/structure index (21 ADRs; full tree).
- **Six new authoritative artifacts** created (state map, drift analysis, architecture status summary,
  release-history reconstruction, alignment report, AP-104 report).

## Current project reality (one paragraph)

Nexus is a **production-grade governed-execution kernel** — un-bypassable approval gate, 11-gate
runtime governance, event-sourced memory, and a production-quality communication outbox, all tested —
now fronted by an **operational single-node autonomy layer**: the v1.0.1 scheduler drives research,
briefing, approval-expiry, metrics-aggregation, and read-only health jobs, all audited. The honest
caveats: **concrete agent runtimes are still stubbed (Gemini/Claude) or mocked (Hermes)**, the
**default sandbox provides no isolation**, health/`status` reporting is shallow, and Alembic migrations
are incomplete. It is **pilot-ready as an attended-to-lightly-autonomous single-operator control
plane** — not yet a fully autonomous, multi-runtime platform.

## Authoritative sources going forward

| For… | Read |
|---|---|
| Per-subsystem built status (canonical) | `blueprint/implementations/v1.0.1/architecture-status-summary.md` |
| Current project status | `blueprint/STATUS.md` |
| History + direction | `blueprint/ROADMAP.md` + `release-history-reconstruction.md` |
| Reality vs design | `documentation-drift-analysis.md` |
| What exists on disk | `repository-state-map.md` |

The numbered `docs/` are **design-intent** (target architecture), not current status.

## Remaining documentation debt

All remaining inaccuracies are **code-scoped** (out of this documentation-only AP) and are logged with
owners rather than silently fixed:

1. **Version string** — `nexus/__init__.py` & `pyproject.toml` still read `0.1.0` vs tag `v1.0.0`
   (one-line code change; future code AP or release commit).
2. **`/api/v1/status`** reports subsystems as `"stub"`; **health** is a boot-time boolean, not live.
3. **Hermes capability ledger** — deferred to **AP-105** (Hermes Reality Audit).
4. **Sandbox safety** configuration audit — deferred to **A-006**.
5. **Alembic completion / PostgreSQL path** — future code work.

## Overall documentation accuracy score

**Before AP-104: ~3.0 / 10** — primary docs (README/STATUS/ROADMAP/CHANGELOG) actively misrepresented
the system as pre-build; the decision record was under-indexed.

**After AP-104: 9.0 / 10** — all primary documents are truthful, internally consistent (single status
source of truth), and cross-evidenced against code and git. The deduction reflects the deliberately
deferred, **code-scoped** residual debt above (version string, live health/`status`, Hermes ledger,
sandbox audit) — none of which a documentation-only AP may resolve. Those close out via AP-105, A-006,
and a small future version-sync code change.

---

*AP-104 deliverables: `blueprint/implementations/v1.0.1/{repository-state-map, documentation-drift-analysis,
architecture-status-summary, release-history-reconstruction, documentation-alignment-report,
AP-104-report}.md`. No source files were modified.*
