# Architecture Decision Records — Nexus v2

This directory holds v2's Architecture Decision Records — the "why," not the "what" (the "what" lives in
`docs/v2/`). Nexus v1 has its own, separately-numbered ADR series at `blueprint/DECISIONS/`; the two are
intentionally on different numbering tracks — see **Numbering collisions** below before assuming a number
means the same thing in both series.

This page is the canonical ADR navigation page: for every ADR, it gives status, motivation, what it
touches, what it depends on, and where it shipped. For the full ratification narrative (not just this
table), see [`docs/v2/ADR_RATIFICATION_REPORT.md`](../docs/v2/ADR_RATIFICATION_REPORT.md). For the full
audit this table was built from — numbering, chronology, cross-references, the ADR-005/006 investigation,
and a traceability matrix — see
[`docs/DOCUMENTATION_PHASE5_REPORT.md`](../docs/DOCUMENTATION_PHASE5_REPORT.md).

| ADR | Title | Status | Date | Motivation | Impacted subsystems | Related ADRs | Implementation references | Release introduced |
|---|---|---|---|---|---|---|---|---|
| [001](ADR-001.md) | Persistence & State Model | Accepted | 2026-06-26 | Three undecided candidate sources of truth (event log / state store / checkpoint store) made replay, recovery, and audit unreliable. | Event sourcing substrate; State; Checkpoint; Recovery; Knowledge | Informs 002, 003, 004, 007; depended on by 007, 008, 009 | `nexus_core/persistence/interfaces.py`, `nexus_infra` (event store, projections, checkpoints) | v2.0.0 |
| [002](ADR-002.md) | Registry Architecture | Accepted | 2026-06-26 | Six overlapping registries (Capability/Resource/Runtime/Harness/Skill/Policy) had no single owner for provider health/availability. | Capability Registry; Harness Registry (subsumes Runtime); Skill Registry; Policy Registry; Orchestration (allocation) | Depends on 001; depended on by 009 | `nexus_runtime` (Harness/allocation), `nexus_orchestration`, `contracts/capability.md`, `contracts/resource.md` | v2.0.0 |
| [003](ADR-003.md) | Canonical Object Model | Accepted | 2026-06-26 | Seven object-model contradictions (Goal undefined, Work Package defined thrice, Execution Graph containment, Observation dual ownership, "Intent Resolution"/"Executive Intelligence" naming, Validation enum drift, Artifact dual vocabulary). | Goal; Work Package; Execution Graph; Validation; Artifact; Intent Resolution naming | Depends on 001 | `contracts/goal.md`, `contracts/intent.md`, `contracts/work_package.md` (§3.5 naming fix verified still correctly propagated as a historical-alias note in both contracts and `docs/v2/01_ARCHITECTURE.md`/`02_OBJECT_MODEL.md`) | v2.0.0 |
| [004](ADR-004.md) | Policy Engine & Governance | Accepted | 2026-06-26 | Undefined policy language/conflict metric, two incompatible approval taxonomies, Policy/Recovery decision-ownership overlap, an over-broad determinism claim. | Policy Engine; Governance; Recovery (boundary only); Execution Strategy approval levels | Depends on 001; informs 008, 009 | `nexus_policy` (engine, defaults, precedence), `contracts/policy.md` | v2.0.0 |
| — | *(ADR-005 — never filed; see investigation)* | **Gap — never written** | n/a | Referenced as a planned decision (reinstate **Engineering Intelligence** as a distinct Reason capability; retire "Executive Intelligence"; move work-classification out of Intent Resolution). | Engineering Intelligence (Reason capability) | Distinct from 003's naming fix (which *was* ratified); referenced alongside 006 | Substance shipped anyway: `nexus_engineering` package exists and is named "Engineering Intelligence" throughout | n/a — no ADR file, decision undocumented as a standalone record |
| — | *(ADR-006 — never filed; two conflicting definitions drafted; see investigation)* | **Gap — never written** | n/a | Definition A (`ARCHITECTURE_CONSTITUTION.md`/`CONSTITUTIONAL_MIGRATION_BLUEPRINT.md`/`IMPLEMENTATION_READINESS_REVIEW.md`): name Policy/Repository Intelligence/Human Interaction/Actuation/Operations as first-class subsystems. Definition B (`CONSTITUTIONAL_ENGINEERING_PROGRAM.md` §7 + its own WP-P0.7): ratify ADR roadmap ordering ("Program Sequencing," front-loading Policy + ADR-007/008). | Policy; Repository Intelligence; Human Interaction; Operations; program build order | Definition B's substance was ratified — absorbed into 008 (confirmed by `ADR_RATIFICATION_REPORT.md`'s own C6 status note) rather than filed under its own number | Definition A's substance shipped anyway: `nexus_policy`, `nexus_repository`, `nexus_human_interaction`, `nexus_operations` all exist as packages (Actuation remains a composite stage across Orchestration/Harness/Runtime/Execution, consistent with how the Constitution itself describes it, not a gap) | n/a — no ADR file for definition A |
| [007](ADR-007-persistence-authority.md) | Persistence Authority | Accepted | 2026-07-13 | Add durability behind the existing synchronous protocols without an async rewrite; resolve where v1's mutable tables sit relative to the event log. | Durable event store; checkpoint store; v1-table-to-projection migration | Depends on 001; depended on by 008 | `nexus_core/persistence/interfaces.py`, `contracts/event.md`, `contracts/checkpoint.md` | v2.0.0 |
| [008](ADR-008-shadow-migration.md) | Shadow Migration | Accepted | 2026-07-13 | Define how v1 decision-owners migrate to v2 one at a time without a big-bang cutover or unproven behavior change. | Migration mechanism (Recorded Shadow Adjudication); Policy Engine (migrates first); every per-owner migration P2–P10 | Depends on 007, 001, 004; absorbs ADR-006 Definition B's sequencing decision | `docs/v2/P0_ADR008_SHADOW_MIGRATION_SPIKE.md`; migration mechanism per-owner rollout (feature-flagged) | v2.0.0 |
| [009](ADR-009-runtime-selection-ownership.md) | Runtime Selection Ownership | **Proposed** (unratified) | 2026-07-21 | INV-37's wording says Orchestration selects/allocates runtimes; the shipped code (and the runtime subsystem's own frozen design docs) has the Runtime Manager doing it instead — an internal contradiction against INV-02 (single ownership). | Runtime Manager; Orchestration; Execution/Actuation dispatch seam | Depends on 002; consistent with 001, 004 | `nexus_runtime/allocation.py` (`RuntimeSelector`), `nexus_execution/actuation/dispatch.py` (the docstring that asserts "joint ownership" in one place and names Runtime Manager sole owner in another — the exact contradiction this ADR proposes to resolve) | v2.0.0 (shipped **unratified** — a disclosed known limitation, not silently pending) |

## Numbering collisions (by design, not an error)

Nexus v1's ADR series lives at `blueprint/DECISIONS/` and is numbered independently. Every v2 number
below has a same-numbered, unrelated v1 counterpart; each is resolved by series, never by number alone:

| Number | v2 decision (this directory) | v1 decision (`blueprint/DECISIONS/`) |
|---|---|---|
| 001 | Persistence & State Model | `ADR-001-tech-stack.md` |
| 002 | Registry Architecture | `ADR-002-database-choice.md` |
| 003 | Canonical Object Model | `ADR-003-pi-evaluation.md` |
| 004 | Policy Engine & Governance | `ADR-004-memory-architecture.md` |
| 005 | *(gap — never filed, see investigation)* | `ADR-005-agent-routing.md` |
| 006 | *(gap — never filed, see investigation)* | `ADR-006-approved-tech-stack.md` |
| 007 | Persistence Authority | `ADR-007-email-provider.md` |
| 008 | Shadow Migration | `ADR-008-discord-authorization.md` |
| 009 | Runtime Selection Ownership (Proposed) | `ADR-009-approval-expiration.md` |
| 010 | *(planned, unwritten — correlation-event gateway / INV-39 transport freeze)* | `ADR-010-execution-timeouts.md` (Accepted, ratified, and actively cited in code: `nexus/execution/runners/*.py`, `docs/v1/ORCHESTRATION.md` §6.1) |

**The ADR-010 row matters in a way 005–009 don't: v1's ADR-010 is real, ratified, and implemented** — it is
not a gap of any kind, and must not be confused with v2's own unwritten, differently-scoped ADR-010
(the correlation-event gateway). This distinction was previously undocumented in this index; it is added
here because Phase 5's audit found it while tracing every ADR-010 reference repository-wide.

**Numbering note — `ADR-005`/`ADR-006` do not exist as files in this directory.** This is a known, tracked
gap (`docs/DOCUMENTATION_MASTER_PLAN.md` §1.7/§5) investigated in full in
[`docs/DOCUMENTATION_PHASE5_REPORT.md`](../docs/DOCUMENTATION_PHASE5_REPORT.md) §2. Summary: neither number
was ever a file (confirmed against full git history — nothing to recover), but the decisions they were
meant to record were real and were substantively carried out in shipped code; the ADR paperwork was simply
never completed. This documentation initiative does not invent or ratify decisions, so it is not resolved
here — formalizing (or formally disclaiming) those two references remains future work, now precisely
scoped rather than an open question.

**ADR-010** (the v2 correlation-event gateway / INV-39 transport freeze) is referenced as a planned-but-
unwritten ADR in `docs/v2/ADR_RATIFICATION_REPORT.md` and remains unwritten.
