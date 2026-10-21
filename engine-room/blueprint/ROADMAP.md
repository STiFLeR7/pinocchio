# Nexus — Project Roadmap

Version: aligned to v1.0.0 + v1.0.1 (Alignment)
Last Updated: 2026-06-24
Status: Active
Full reconstruction: [release-history-reconstruction.md](implementations/v1.0.1/release-history-reconstruction.md)

> Realigned in AP-104 (v1.0.1). The prior version froze phase statuses at "Phase 1 complete / Phase 2
> next," which inverted reality. This roadmap now records the **true delivered history** and the
> genuinely-forward direction. Per-phase Goals/Achievements/Lessons/Deferred live in the reconstruction.

---

## Vision

Nexus becomes a trusted operational control plane that continuously manages tasks, context, approvals,
research, and execution while remaining transparent, recoverable, and governed by human intent.

---

## Release Strategy (actual)

| Release | State | Scope |
|---|---|---|
| Phases 0–3 + 8 | ✅ Delivered | Foundation → Core → MVP → Execution/Registry/Governance; Pi evaluation |
| **v1.0.0** "Operational Intelligence" | ✅ Released (tag `v1.0.0`) | Governed execution + research/briefing/outbox/metrics/governance |
| **v1.0.1** "Alignment" | 🔄 In progress | Correctness/safety/operational-completeness (no features) |
| Future | ⚪ Planned | Distributed scheduling, PostgreSQL, extended integrations, runtime de-stubbing |

---

## Development Philosophy

Nexus is built **vertically**: one complete, tested workflow at a time. Every phase produces a usable,
tested system; nothing progresses on an unstable base. (Validated in practice — see reconstruction.)

---

## Delivered Phases

### Phase 0 — Project Foundation — ✅ Complete
Production-ready skeleton: packaging, Pydantic config, structlog, async SQLAlchemy/SQLite, pytest,
Docker, GitHub Actions CI, FastAPI health skeleton. (AP-001…AP-010.)

### Phase 1 — Core Infrastructure — ✅ Complete
DB foundation, EventGateway + transactional outbox, event-sourced memory manager with checkpoint
replay, task engine, **approval engine (un-bypassable gate)**, state-machine validation.

### Phase 2 — Task Management / MVP Workflow — ✅ Complete
Full task lifecycle and the end-to-end task→approval→execution→summary MVP with Discord integration;
integration-stability and product-acceptance validation.

### Phase 3 — Execution Runtime, Registry & Governance — ✅ Complete
Runtime registry + CLI/Agent adapter split; Gemini (AP-301), Runtime V2 + `agent_steps` (AP-302A),
Nexus adapter (AP-303A), Claude adapter + registry validation (AP-302B), runtime selection (AP-303B),
repository governance hardening (AP-304); **11-gate governance**; research + briefing designs.
*Lesson:* concrete runtimes shipped as shell **stubs/mocks** — addressed by A-005/AP-105.

### Phase 8 — Pi Evaluation (parallel) — ✅ Complete
Evaluated Pi; **ADR-003 = reject**, adopt custom Python orchestration borrowing Pi's event-loop /
queue / parallel-execution concepts.

---

## v1.0.0 — "Operational Intelligence" — ✅ Released

Tagged `v1.0.0`. Delivered the governed-execution platform with research engine, briefing engine,
communication outbox, metrics persistence, and runtime governance. Accepted onboarding audit
(maturity **6.0/10**) surfaced six findings (A-001…A-006) that became the v1.0.1 backlog —
notably a **documented-but-unbuilt scheduler**, fail-open owner auth, and a silent timeout bug.

---

## v1.0.1 — "Alignment" — 🔄 In progress

Correctness, safety, and operational completeness. **No new features**; every change traces to an
accepted audit finding.

| AP / Finding | Scope | Status |
|---|---|---|
| AP-101 | Audit validation | ✅ Complete |
| AP-102 / A-001 | Fail-closed owner auth (startup + engine) | ✅ Complete |
| AP-102 / A-002 | Execution-timeout correctness (ADR-010 + `hard_limit`) | ✅ Complete |
| AP-103 / A-003 | Scheduler foundation (design + implementation, single-node, 6 jobs) | ✅ Complete |
| AP-104 / A-004 | Documentation alignment | ✅ Complete |
| AP-105 / A-005 | Nexus reality audit (verdict: Prototype) | ✅ Complete |
| A-006 | Sandbox safety review (verdict: Unsafe By Default) | ✅ Complete |
| v1.1.0 Track S | Sandbox hardening (S-2/S-3/S-4) → **Pilot Safe** (`ADR-sandbox-pilot-safe`) | ✅ Complete (committed `b734c13`, tag `track-s-pilot-safe`) |
| v1.1.0 Track H — H-2 | Nexus honesty fixes → **Experimental** (`ADR-hermes-experimental`) | ✅ Complete (pending freeze commit) |
| v1.1.0 Track H — H-4 | Nexus lifecycle safety → **Pilot** (terminate/resume/budget/timeout) | 🔲 Planned (`H-4-scope-definition.md`) |

---

## Future (genuinely not started)

| Theme | Description | Status |
|---|---|---|
| Runtime de-stubbing | Real Gemini/Claude CLI integration (Nexus de-mocked in v1.1.0 H-2 → Experimental) | ⚪ Future |
| Distributed scheduling | Cross-process lease, multi-node (see `scheduler-future-scaling.md`) | ⚪ Future |
| PostgreSQL backend | Migrate from SQLite/WAL; complete Alembic (ADR-002) | ⚪ Future |
| Extended integrations | WhatsApp, Slack, GitHub | ⚪ Future (Phase 9) |
| Advanced memory | Vector / knowledge graph | ⚪ Future (Phase 10) |
| Multi-agent coordination | Hierarchical agents | ⚪ Future (Phase 11) |
| Live health + observability | Real DB/Discord/OpenRouter probing; `/api/v1/status` de-stub | ⚪ Future |

---

## A note on AP numbering

Historical phase APs (e.g. "Phase 1 / AP-101") and v1.0.1 release APs (e.g. "AP-101 Audit Validation")
share the `AP-1xx` prefix but are **different namespaces**. v1.0.1 APs are written "AP-10x (v1.0.1)".
See the reconstruction for the full mapping.

---

## Status Legend

| Symbol | Meaning |
|---|---|
| 🔲 | Not Started |
| 🔄 | In Progress |
| ✅ | Complete |
| ⚪ | Future |
| ❌ | Blocked |
