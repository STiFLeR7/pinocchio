# Documentation Drift Analysis (AP-104)

> Per-document drift analysis measuring every major project document against
> `repository-state-map.md` (ground truth). Format per the AP-104 mandate:
> **Document · Current Claims · Actual Repository Reality · Drift Severity · Required Corrections ·
> Evidence.**
>
> Severity scale: 🔴 Critical (actively misleads about what exists/safety) · 🟠 High (materially wrong
> phase/version/status) · 🟡 Medium (stale lists, broken links) · 🟢 Low (cosmetic).

---

## 1. `README.md` — 🔴 Critical

| Field | Detail |
|---|---|
| **Current claims** | Status badge **pre-alpha**; version **0.1.0**; Python **3.11+**; "Setup instructions will be published when Phase 0 is complete"; Development-Status table shows **all 8 phases 🔲 Pending**; runtimes listed as future; no mention of governance, scheduler, outbox, metrics, research/briefing as built. |
| **Actual reality** | Released **v1.0.0** (tag); Python **3.12+**; Phase 0–1 complete and far beyond — approval gate, 11-gate governance, runtime registry, research/briefing engines, communication outbox, metrics, and the v1.0.1 scheduler all shipped. |
| **Severity** | 🔴 Critical — a reader is told the project has not started building. |
| **Required corrections** | Rewrite status/version/Python badges; replace phase table with truthful release+subsystem status; add real capabilities, runtime support, governance, scheduler, sandboxing sections; correct quick-start; link to ADRs and `architecture-status-summary.md`. |
| **Evidence** | `README.md:5-7,142-161`; reality `repository-state-map.md` §1–§3. |

## 2. `blueprint/STATUS.md` — 🔴 Critical

| Field | Detail |
|---|---|
| **Current claims** | Date 2026-06-20, **Version 0.1**, "**Phase 1 Completed**", "next immediate step is **Phase 2**", "23 unit tests", phases 2–7 **Not Started**. |
| **Actual reality** | v1.0.0 released + v1.0.1 alignment in progress; **143 tests** pass (v1.0.1); approvals, execution, governance, research, briefing, outbox, metrics, scheduler all built; Phases 2–7 are substantially delivered (under a later AP-numbering scheme). |
| **Severity** | 🔴 Critical — claims the system stops at infrastructure. |
| **Required corrections** | Rewrite to v1.0.0/v1.0.1 reality with a per-subsystem Completed/Operational/Experimental/Deferred classification (mirror `architecture-status-summary.md`); correct test count; correct "next steps" to remaining v1.0.1 APs. |
| **Evidence** | `blueprint/STATUS.md:3-5,26-34,56-68`; reality `09-operational-capabilities.md`, scheduler reports. |

## 3. `blueprint/ROADMAP.md` — 🟠 High

| Field | Detail |
|---|---|
| **Current claims** | Version 0.1; Phases 0,1,8 ✅; **Phases 2,3,4,5,6,7 all 🔲 Not Started**; release strategy v0.1/v0.5/v1.0 future. |
| **Actual reality** | Phases 2–7 work is delivered (task lifecycle, approval engine + Discord, execution runtime + runners, research automation, intelligence/briefing reporting, hardening) and the product is released as v1.0.0 with a v1.0.1 alignment line. |
| **Severity** | 🟠 High — phase statuses invert reality. |
| **Required corrections** | Reconstruct as project history (Phase 0…v1.0.0…v1.0.1…Future) with Goals/Achievements/Lessons/Deferred per `release-history-reconstruction.md`; mark delivered phases ✅; reframe "Future" to the genuinely-future items (distributed scheduler, PostgreSQL, multi-node, extra runtimes). |
| **Evidence** | `blueprint/ROADMAP.md:3,119-275`; reality `repository-state-map.md` §3. |

## 4. `CHANGELOG.md` — 🟠 High

| Field | Detail |
|---|---|
| **Current claims** | Only `[Unreleased]` (initial scaffolding) and `[0.0.1] 2026-06-19` (repo init). No v1.0.0, no v1.0.1. |
| **Actual reality** | v1.0.0 released (tag `v1.0.0`, commits `4566020`/`aa3e527` "Operational Intelligence"); v1.0.1 Alignment delivering A-001/A-002 safety fixes and A-003 scheduler. |
| **Severity** | 🟠 High — the change record omits the actual releases. |
| **Required corrections** | Add `[1.0.0]` and `[1.0.1]` (Unreleased) sections reconstructed from git history + v1.0.1 AP reports; keep Keep-a-Changelog format. |
| **Evidence** | `CHANGELOG.md:9-40`; `git tag`, `git log` (`aa3e527`,`4566020`). |

## 5. `blueprint/README.md` (landing page) — 🟡 Medium

| Field | Detail |
|---|---|
| **Current claims** | ADR list shows only ADR-001..003; structure tree implies a small `phases/` tree. |
| **Actual reality** | 21 ADRs exist; `implementations/`, `onboarding/`, `reports/`, `architecture/` trees are large and authoritative. |
| **Severity** | 🟡 Medium — landing page under-represents the decision record. |
| **Required corrections** | Update ADR pointer to reflect 21 ADRs (or point to the `DECISIONS/` directory as the index); add `onboarding/`, `implementations/`, `reports/`, `architecture/` to the structure. |
| **Evidence** | `blueprint/README.md:21-27`; `repository-state-map.md` §6. |

## 6. `docs/06_DEVELOPMENT_PHASES.md` and `docs/*` design docs — 🟡 Medium (planned-as-built)

| Field | Detail |
|---|---|
| **Current claims** | The numbered `docs/` describe the **target** architecture/phasing in future tense (incl. a planned scheduler, planned research/briefing/outbox). |
| **Actual reality** | Most of the target is now built; the design docs read as roadmap, not status. |
| **Severity** | 🟡 Medium — these are *design-intent* docs, legitimately aspirational, but lack a "now built" pointer, so a reader can mistake design for current state. |
| **Required corrections** | Do **not** rewrite design docs (out of scope and they remain valid as intent). Add a single status banner/pointer at the top of `docs/` consumption points (README "Documentation" table) directing readers to `architecture-status-summary.md` for *current* status. (Banner added via README; design-doc bodies left intact.) |
| **Evidence** | `docs/06_DEVELOPMENT_PHASES.md`; `README.md:194-208`. |

---

## 7. Special-attention scan (AP-104 mandated terms)

Searched the project docs for language describing already-built subsystems as future/planned:

| Term / claim | Found in | Built? | Verdict |
|---|---|---|---|
| "pre-alpha" | `README.md:5` | n/a (released v1.0.0) | 🔴 Drift — corrected |
| "Phase 0 not complete" / setup pending | `README.md:161` | Phase 0–1 complete | 🔴 Drift — corrected |
| Planned Scheduler | `docs/`, ROADMAP AP-505/606 | **Built** (v1.0.1) | 🟠 Drift — ROADMAP reclassified ✅ |
| Planned Research Engine | ROADMAP Phase 5 🔲 | **Built** (un-triggered → now scheduled) | 🟠 Drift — reclassified |
| Planned Briefing Engine | ROADMAP Phase 6 🔲 | **Built** + scheduled 08:00 | 🟠 Drift — reclassified |
| Planned Outbox | ROADMAP/STATUS | **Built** (production-grade) | 🟠 Drift — reclassified |
| Planned Metrics Persistence | STATUS | **Built**; aggregation now scheduled | 🟠 Drift — reclassified |
| "Future Runtime Registry" | ROADMAP Phase 4 🔲 | **Built** (registry + adapter split) | 🟠 Drift — reclassified |
| Prototype / "23 unit tests" | `STATUS.md:19` | 143 tests | 🟠 Drift — corrected |

No occurrences describe a **non-existent** subsystem as built (the inverse, healthier failure mode) —
**except** the original v1.0.0-era docs/ADRs that leaned on a scheduler that did not exist; that gap is
now genuinely closed by v1.0.1, so those references became *accurate retroactively*.

---

## 8. Residual drift (out of AP-104 scope — documented, not fixed)

| Item | Why deferred | Recommended owner |
|---|---|---|
| `nexus/__init__.py` / `pyproject.toml` `version = "0.1.0"` vs tag `v1.0.0` | Source/config edit — AP-104 is documentation-only | A one-line version-sync change in a code AP (or the v1.0.1 release commit) |
| `requires-python >=3.12` vs README "3.11+" | README is doc (fixed here); the *authoritative* value lives in pyproject (code) | README corrected to 3.12+; pyproject already correct |
| `/api/v1/status` reports subsystems as literal `"stub"` | Source behavior, not a doc | Note in STATUS as a known reporting gap; fix in a future code AP |
| Nexus precise capability ledger | Belongs to AP-105 (Nexus Reality Audit) | AP-105 |
| Sandbox default-off security posture | Belongs to A-006 sandbox review | A-006 |

These are recorded in `documentation-alignment-report.md` and the final summary as
**remaining documentation debt**, not silently dropped.
