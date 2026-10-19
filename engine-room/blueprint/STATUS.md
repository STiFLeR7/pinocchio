# Nexus — Project Status

Date: 2026-06-24
Release: v1.0.0 ("Operational Intelligence", git tag `v1.0.0`)
Active line: v1.0.1 ("Alignment") — in progress
Authoritative subsystem status: [architecture-status-summary.md](implementations/v1.0.1/architecture-status-summary.md)

> This file was realigned in AP-104 (v1.0.1) after the accepted onboarding audit found it frozen at
> "Phase 1." It now reflects the **actual** repository state, verified first-hand.

---

## Current State

Nexus is a **released governed-execution control plane** (v1.0.0) currently undergoing the v1.0.1
"Alignment" correctness/safety pass.

It is **pilot-ready as an attended, single-operator governed-execution console** with a now-operational
single-node autonomy layer. The production-grade core is the approval gate + 11-gate governance +
event-sourced memory + transactional/communication outbox. The v1.0.1 line has already closed the
three Priority-0/1 findings (fail-closed owner auth, execution-timeout correctness, and the previously
missing scheduler).

**Test suite:** 143 tests passing (v1.0.1); ruff clean; mypy strict clean (57 source files).

---

## Subsystem Status

| Subsystem | Classification | Basis |
|---|---|---|
| Approval System | ✅ Completed / Operational | Un-bypassable DB gate; **fail-closed** owner auth (A-001) |
| Runtime Governance (11-gate) | ✅ Completed / Operational | Audits every decision; best-tested code |
| Memory System (event-sourced) | ✅ Completed / Operational | Immutable `audit_log` + checkpoint replay |
| Communication Outbox | ✅ Completed / Operational | Lease-based, backoff, dead-letter, audited |
| Task Management | ✅ Completed / Operational | Guarded lifecycle, locking, Discord CRUD |
| Runtime Registry + adapter split | ✅ Operational | Extensible CLI/Agent abstraction |
| Execution timeouts | ✅ Operational | Honors ADR-010 + `hard_limit` clamp (A-002) |
| Scheduler (single-node) | ✅ Operational | 6 audited jobs (new in v1.0.1, A-003) |
| Metrics persistence | ✅ Operational | Collection + scheduled aggregation/retention |
| Research engine | 🟡 Operational (latent) | Built + scheduled; empty feeds by default → audited-skip |
| Daily briefing engine | 🟡 Operational | Built + scheduled 08:00 Asia/Kolkata |
| Gemini runtime | 🟠 Stubbed | Generic shell runner (no real CLI binary) |
| Claude runtime | 🟠 Stubbed | Generic shell runner (no real CLI binary) |
| Nexus runtime | 🟠 Experimental | Honest: no prod mock, provider-backed search, goal-derived plans, structured calls, truthful outcomes (v1.1.0 H-2, effective on commit). Lifecycle safety = Pilot/H-4 |
| Sandbox isolation | 🟢 Pilot Safe | Default-secure fail-closed + boot-validated + workspace-confined (v1.1.0 Track S, effective on commit); isolation opt-in. Residual R-04/R-08/R-09 |
| Health reporting | 🟠 Experimental | Boot-time boolean; `/api/v1/status` reports `"stub"` |
| Alembic migrations | 🟠 Experimental | `create_all` is current schema source; migrations incomplete |
| Distributed scheduling / PostgreSQL / extra integrations | ⚪ Future | Designed/aspirational |

Classification legend: ✅ Completed/Operational · 🟢 Pilot Safe (default-secure, supervised-pilot grade) ·
🟡 Operational (latent/partial) · 🟠 Experimental/Stubbed · 🔴 Mocked · ⚪ Future. Authoritative detail
in `architecture-status-summary.md`.

---

## v1.0.1 "Alignment" progress

| AP | Scope | Status |
|---|---|---|
| AP-101 | Audit validation (all 6 findings confirmed first-hand) | ✅ Complete |
| AP-102 | Critical safety fixes — A-001 fail-closed, A-002 timeout correctness | ✅ Complete |
| AP-103 | Scheduler foundation — design + implementation (A-003) | ✅ Complete |
| AP-104 | Documentation alignment (A-004) | ✅ Complete |
| AP-105 | Nexus reality audit (A-005) — verdict Prototype | ✅ Complete |
| A-006 | Sandbox safety review — verdict Unsafe By Default | ✅ Complete |

### v1.1.0 "Containment" (branch `v1.1.0-planning`)

| Track | Scope | Status |
|---|---|---|
| Track S (S-2/S-3/S-4) | Sandbox hardening → **Pilot Safe** (`ADR-sandbox-pilot-safe`) | ✅ Complete (committed `b734c13`, tag `track-s-pilot-safe`) |
| Track H — H-2 | Nexus honesty fixes → **Experimental** (`ADR-hermes-experimental`) | ✅ Complete (pending freeze commit) |
| Track H — H-4 | Nexus lifecycle safety → **Pilot** (terminate/resume/budget/timeout) | 🔲 Planned (`H-4-scope-definition.md`) |

---

## Immediate Next Steps

1. **H-4 (Pilot)** — Nexus lifecycle safety: fail-fast init, configurable budget, terminate +
   cancellation wiring, `TIMED_OUT`, `resume_goal`, one audited real run (`H-4-execution-roadmap.md`).
2. **Residual code-debt** (separate code AP): sync in-code version string (`__init__.py`/`pyproject`
   `0.1.0` → `1.x`), live health probing, Alembic completion.

---

## Blocking Issues

None. (Known risks are tracked as v1.0.1 findings A-005/A-006 and residual debt, not blockers.)

---

## Notes

- **Version-string drift:** the in-code version is still `0.1.0` while the release tag is `v1.0.0`.
  Correcting it is a source/config change, intentionally out of AP-104's documentation-only scope; it
  is logged as residual debt (see `documentation-drift-analysis.md`).
- The numbered `docs/` are design-intent; this file + `architecture-status-summary.md` are the
  authoritative status sources.
