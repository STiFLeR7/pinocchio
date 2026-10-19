# Scheduler Readiness Review (AP-103, design gate)

> Go/No-Go readiness assessment for the Scheduler Foundation design, before any implementation.
> This is the AP-103A decision input. Design only.

---

## 1. Constraint compliance checklist

| # | Constraint | Met by design? | Evidence |
|---|---|---|---|
| 1 | No service-boundary violations | ✅ | Scheduler in top layer; imports services only (`scheduler-design.md §2-4`) |
| 2 | No direct DB model access | ✅ | Jobs open session, hand to services; never import `models` (§4, event-map §5) |
| 3 | Interact through existing services | ✅ (J1–J4) / ⚠ (J5–J6) | J1–J4 use existing methods; J5/J6 need NEW read-only service methods |
| 4 | Replaceable | ✅ | `SchedulerPort` Protocol + `APSchedulerAdapter` |
| 5 | APScheduler preferred | ✅ | `AsyncIOScheduler` |
| 6 | Future distributed scheduling | ✅ | Port abstraction + jobstore swap + idempotency (`recovery-model §6`) |
| 7 | No business logic in jobs | ✅ | Job contract (§4) |
| 8 | Jobs invoke services only | ✅ | Job contract (§4) |
| 9 | Failures auditable | ✅ | `failure-model §4`, `event-map §3` |
| 10 | Restart-safe | ✅ | `recovery-model §1-4` |

## 2. Capability classification (the decisive readiness question)

| Job | Classification | Ready to schedule with zero new code? |
|---|---|---|
| J1 Research Collection | **Existing** (+ Derived feeds config) | Needs a feeds config source (additive) |
| J2 Daily Briefings | **Existing** | ✅ |
| J3 Approval Expiration Sweep | **Existing** | ✅ |
| J4 Metrics Aggregation | **Existing** | ✅ |
| J5 Outbox Health | **New (read-only observability)** | ✗ needs thin read-only service |
| J6 Checkpoint Health | **New (read-only observability)** | ✗ needs thin read-only service |

## 3. Risks & open decisions for AP-103A

| ID | Item | Recommendation |
|---|---|---|
| D-1 | **J5/J6 require new read-only code** — tension with "no new features" | Approve as **observability scope** (no behavior/feature change), OR **defer J5/J6** to a later AP and ship J1–J4 now |
| D-2 | **J1 research feeds** has no config source | Approve an additive `scheduling.research.feeds` config list at AP-103B; until then J1 cannot run |
| D-3 | **Scheduler EventType additions** (`SCHEDULER_JOB_*`) | Approve additive enum values, or fall back to generic audit with `component="scheduler"` |
| D-4 | **SQLite write contention** amplified by job writers (RISK-002) | Stagger intervals; rely on `busy_timeout` + idempotency; revisit when moving to PostgreSQL |
| D-5 | **ADR-009 expiry semantics** (J3 cancels task vs. notify/review) | Out of A-003 scope; **do not** change in AP-103; track separately |
| D-6 | **No persistent jobstore in v1** | Acceptable given idempotency; persistent/distributed jobstore is a documented future step |

## 4. Explicit non-goals (scope fences)

- No generic auto-resume recovery supervisor (TD-22) — J6 only observes.
- No change to governance, health semantics, approval expiry behavior, or runtime execution.
- No new product/user-facing feature; J5/J6 are observability only.

## 5. Recommended go/no-go

**GO for AP-103A approval of the design**, with two decisions required from the owner before
AP-103B implementation:
1. **J5/J6:** approve as read-only observability **or** defer (D-1).
2. **J1 feeds + scheduler audit enum:** approve the additive config + enum values (D-2, D-3).

If the owner declines any new code whatsoever, the **minimum viable scheduler** is **J2 + J3 + J4**
(all Existing Capabilities, zero new code beyond the scheduler wiring itself), with J1 added once a
feeds source is approved and J5/J6 deferred.

## 6. Readiness score

Design completeness: **High.** All ten constraints satisfied by design; every job analyzed; the two
ambiguous jobs (J5/J6) honestly classified with a deferral fallback. **Ready for AP-103A decision.**
