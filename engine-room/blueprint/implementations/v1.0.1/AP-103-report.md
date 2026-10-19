# AP-103 — Scheduler Foundation (Design) — Report

> **Release:** Nexus v1.0.1 "Alignment" · **AP:** AP-103 · **Type:** Design & architecture only.
> **Status:** ✅ Design complete — PROPOSED, pending AP-103A approval.
> **Source changes:** NONE (verified). **Finding:** A-003.

---

## 1. Objective

Design the minimum scheduler architecture to operationalize the already-existing Research, Briefing,
Approval-expiration, and Metrics-aggregation capabilities, plus the two audit-requested health
monitors — without implementing anything.

## 2. Method

Confirmed the real service interfaces, audit mechanism, and the (non-)existence of outbox/checkpoint
health surfaces at commit `aa3e527`, then produced an evidence-grounded design that satisfies all
ten AP-103 constraints. No code, migrations, wiring, config, or behavior changes were made.

## 3. Deliverables produced

| Deliverable | Location |
|---|---|
| `scheduler-design.md` (incl. per-job analysis + Mermaid) | `blueprint/implementations/v1.0.1/` |
| `scheduler-event-map.md` | `blueprint/implementations/v1.0.1/` |
| `scheduler-failure-model.md` | `blueprint/implementations/v1.0.1/` |
| `scheduler-recovery-model.md` | `blueprint/implementations/v1.0.1/` |
| `scheduler-readiness-review.md` | `blueprint/implementations/v1.0.1/` |
| `scheduler-implementation-plan.md` (AP-103A/B/C/D) | `blueprint/implementations/v1.0.1/` |
| `ADR-scheduler-foundation.md` | `blueprint/DECISIONS/` |
| `AP-103-report.md` (this) | `blueprint/implementations/v1.0.1/` |

## 4. Architecture summary

`AsyncIOScheduler` behind a replaceable `SchedulerPort`, started in the FastAPI lifespan. Six thin
**job wrappers** that contain no business logic and invoke **existing services** only; failures and
lifecycle are audited via `MemoryService.log_event` (`component="scheduler"`) and `record_metric`.
Jobs are declarative + idempotent, so the in-process `MemoryJobStore` is restart-safe without
persistence. Full flow (Scheduler → Jobs → Services → Events → Outbox → Audit Log) plus restart and
failure flows is diagrammed in `scheduler-design.md §7`.

## 5. Special-attention determinations (J5/J6 + feeds)

- **Already implemented?** No — confirmed no read-only health surface exists in `gateway/`, `memory/`,
  or `core/health.py`.
- **Representable as read-only observation?** Yes — both only count/query existing tables and emit
  metrics/audit; no state mutation, no behavior change.
- **Violate "no new features"?** They are **New Capability (read-only observability)** — new *code*
  but not a new *feature*. **Recommendation:** approve as observability scope, or **defer** J5/J6 and
  ship J1–J4.

**Classification:** J1 Research = Existing (+ Derived feeds-config dependency); J2 Briefings =
Existing; J3 Approval Expiry = Existing; J4 Metrics Aggregation = Existing; J5 Outbox Health = New
(read-only); J6 Checkpoint Health = New (read-only).

## 6. Constraint compliance

All ten AP-103 constraints are satisfied by design (matrix in `scheduler-readiness-review.md §1`).
Notably: jobs never access models (constraint 2), invoke services only (7/8), are replaceable (4),
distributed-ready (6), auditable (9), and restart-safe (10).

## 7. Decisions required at AP-103A (before any implementation)

1. J5/J6 — approve as read-only observability **or** defer.
2. J1 — approve an additive `scheduling.research.feeds` config source.
3. Audit — approve additive `SCHEDULER_JOB_*` `EventType` values, or use generic-audit fallback.
4. Confirm job set + cadences.

If new code is declined entirely, the **minimum viable scheduler is J2 + J3 + J4** (all Existing
Capabilities).

## 8. Out of scope (fences)

No implementation; no generic auto-resume recovery supervisor (TD-22 — J6 only observes); no change
to ADR-009 expiry semantics, governance, health, or execution; no documentation (README/STATUS/
ROADMAP) updates (that is AP-104).

## 9. Verification

`git status` shows only new untracked design docs under `blueprint/`; no tracked source files
modified. (Blueprint synchronized for AP-103 scope.)

## 10. Recommendation

**Submit for AP-103A approval.** On approval (with the four decisions recorded), proceed to AP-103B
implementation under TDD per `scheduler-implementation-plan.md`. Awaiting authorization — no
implementation performed.
