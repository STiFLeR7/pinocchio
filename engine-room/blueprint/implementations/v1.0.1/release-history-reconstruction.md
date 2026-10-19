# Release History Reconstruction (AP-104)

> Reconstructs the true project history from the git record and blueprint artifacts, because the
> in-repo STATUS/ROADMAP froze at "Phase 1." Each phase: **Goals · Achievements · Lessons · Deferred
> work.** This is the canonical narrative the rewritten ROADMAP and CHANGELOG draw from.
>
> **Source:** `git log` (28 commits, `e2b0596`→`aa3e527`), blueprint `phases/`, `reports/`,
> `implementations/`, ADRs.

---

## Timeline at a glance (from git)

| Commit | Milestone |
|---|---|
| `e2b0596` | Blueprint + foundational docs initialized |
| `0caf651` | **Phase 0** skeleton complete (tests, lint, types) |
| `5e2ccfe`–`8444f81` | **Phase 8 (parallel)** Pi evaluation → ADR-003 reject, custom orchestration chosen |
| `5cb0411`,`c51da2a` | **Phase 1** Core Infrastructure complete |
| `7337444` | Phase 1 validation + retrospective |
| `8c31e10`,`455cfa0` | **Phase 2** MVP workflow + Discord integration |
| `b3dbf3c`,`fdeab0e` | Phase 2 integration stability + product acceptance |
| `2f0263d`,`53eb8aa` | **Phase 3** plans: runtime, repo governance, research, briefings, command bus |
| `23c5a02` | AP-301 Gemini CLI runtime adapter + governance |
| `e4f70d9` | AP-302A Runtime V2 refactor + `agent_steps` |
| `1652661` | AP-303A Nexus runtime adapter |
| `e3e7a5d` | AP-302B Claude adapter + registry validation |
| `bad6f72` | AP-303B runtime selection framework |
| `7e2bf7a` | AP-304 repository governance hardening |
| `4566020`,`aa3e527` | **v1.0.0 release** "Operational Intelligence" (tag `v1.0.0`) |
| *(working line)* | **v1.0.1 "Alignment"** (AP-101…AP-105) |

---

## Phase 0 — Project Foundation
- **Goals:** production-ready skeleton (packaging, config, logging, DB, CI, Docker, FastAPI).
- **Achievements:** all 10 APs complete; app boots; tests/lint/types green; Docker builds (`0caf651`).
- **Lessons:** investing in strict ruff/mypy + async test harness early paid off across every later phase.
- **Deferred:** real Alembic migration coverage (later proved incomplete — see Lessons in v1.0.0).

## Phase 8 — Pi Evaluation (parallel track)
- **Goals:** decide build-vs-adopt for orchestration before writing a custom orchestrator.
- **Achievements:** full Pi evaluation; **ADR-003 = reject Pi**, adopt custom Python orchestration,
  borrowing Pi's event-loop/queue/parallel concepts (`5e2ccfe`–`8444f81`, `ADR-pi-core-patterns`).
- **Lessons:** the conceptual primitives (context replay, parallel execution) shaped the memory/runtime design.
- **Deferred:** none; track closed.

## Phase 1 — Core Infrastructure
- **Goals:** Nexus Core primitives — DB foundation, event system + transactional outbox, memory
  manager, task engine, approval engine, state-machine validation.
- **Achievements:** event-sourced `audit_log`, checkpoint replay, un-bypassable approval gate, task
  lifecycle, E2E state-machine validation (`5cb0411`); retrospective recorded (`ADR-phase1-retrospective`).
- **Lessons:** event sourcing + outbox made later recovery and Discord-outage tolerance structural, not bolted-on.
- **Deferred:** scheduler (autonomy) explicitly pushed downstream — became the A-003 gap.

## Phase 2 — Task Management / MVP Workflow
- **Goals:** complete, usable task→approval→execution→summary workflow with Discord.
- **Achievements:** MVP workflow end-to-end with Discord integration + type-safety (`8c31e10`);
  integration stability + product acceptance reports (`b3dbf3c`, `fdeab0e`).
- **Lessons:** a vertical, tested workflow beat horizontal feature spread (the roadmap's stated philosophy, validated).
- **Deferred:** richer task query/timeline surface beyond MVP.

## Phase 3 — Execution Runtime, Runtime Registry & Governance
- **Goals:** controlled, auditable multi-runtime execution; repository governance; research/briefing designs.
- **Achievements:** Gemini (AP-301), Runtime V2 refactor + `agent_steps` (AP-302A), Nexus adapter
  (AP-303A), Claude adapter + registry validation (AP-302B), runtime selection framework (AP-303B),
  repository governance hardening (AP-304); 11-gate governance; research + daily-briefing designs.
- **Lessons:** the registry/adapter split is strong, but **concrete runtimes shipped as shell
  stubs/mocks** (Gemini/Claude generic shell; Nexus simulated) — the gap A-005/AP-105 now audits.
- **Deferred:** real CLI binary integration; Nexus de-mocking; command bus (evaluated, `ADR-command-bus-evaluation`).

## v1.0.0 — "Operational Intelligence"
- **Goals:** release the governed-execution platform with intelligence/reporting.
- **Achievements:** tagged `v1.0.0` (`4566020`,`aa3e527`); research engine, briefing engine,
  communication outbox, metrics persistence, runtime governance all present; accepted onboarding audit
  (maturity **6.0/10**).
- **Lessons (from the audit):** (1) docs drifted from code; (2) the **scheduler was documented but never
  built** — autonomy engines were dormant; (3) a silent execution-timeout field-name bug; (4) fail-open
  owner auth; (5) `create_all` (not migrations) is the real schema source; (6) default sandbox = no isolation.
- **Deferred:** everything the audit surfaced → became the v1.0.1 finding set A-001…A-006.

## v1.0.1 — "Alignment" (current line)
- **Goals:** make Nexus honest, safe, and operationally complete — **no new features**; every change
  traces to an accepted audit finding.
- **Achievements (to date):**
  - **AP-101** audit validation (`alignment-validation.md`).
  - **AP-102** safety fixes: **A-001 fail-closed** owner auth (startup + engine); **A-002** timeout
    resolution honoring ADR-010 + `hard_limit` clamp.
  - **AP-103** scheduler foundation **designed and implemented** (A-003): APScheduler, 6 audited jobs,
    single-node, read-only health jobs — 143 tests pass.
  - **AP-104** (this) documentation alignment.
- **Lessons:** the blueprint-as-authority rule only holds if the blueprint is maintained — drift itself
  became a Priority-2 finding.
- **Deferred / remaining:** **AP-105** Nexus reality audit (A-005); **A-006** sandbox safety review;
  in-code version-string sync (0.1.0→1.0.x); live health probing; Alembic completion; distributed
  scheduling + PostgreSQL (genuinely future).

---

## Phase ↔ AP numbering note (resolves a real source of confusion)

The original ROADMAP used **phase-scoped** AP numbers (AP-101 = "Phase 1 / DB Foundation"). The v1.0.1
alignment line **reuses the AP-1xx prefix** for release Action Points (AP-101 = "Audit Validation").
These are **different namespaces**. To avoid ambiguity going forward, v1.0.1 APs are always referenced
as "AP-10x (v1.0.1)" and the historical ones as "Phase-N AP-Nxx". This is documented here so the
reconstructed ROADMAP and STATUS don't appear to contradict the git history.
