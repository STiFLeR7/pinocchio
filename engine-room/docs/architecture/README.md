# Nexus v2 — Architecture Portal

The canonical entry point into Nexus v2's architecture. This page indexes existing documentation — it
does not duplicate it. If a topic below has one authoritative document, this page links to it directly
rather than re-explaining it.

**Brand new — just want to run something first?** Start at
[docs/getting-started/README.md](../getting-started/README.md) (clone to first run in under 15 minutes),
then [docs/tutorials/README.md](../tutorials/README.md) for a guided path through the concepts below.

**Ready for the code-level or design-intent tour?** Start with
[docs/internals/WALKTHROUGH-v2.md](../internals/WALKTHROUGH-v2.md) (a code-level tour) or
[docs/v2/README.md](../v2/README.md) (the design-intent index) before going subsystem-by-subsystem below.

## The Constitution

[`docs/v2/ARCHITECTURE_CONSTITUTION.md`](../v2/ARCHITECTURE_CONSTITUTION.md) is the single normative
document: the thirteen-capability model, the canonical dependency rules, and the full list of ratified
Architectural Invariants (also enumerated standalone in
[`docs/v2/99_ARCHITECTURAL_INVARIANTS.md`](../v2/99_ARCHITECTURAL_INVARIANTS.md)). Every subsystem
below is one capability the Constitution names; none may own a decision another also owns (INV-02).

## Architecture Decision Records

[`adr/README.md`](../../adr/README.md) indexes all seven ratified/proposed ADRs
(`ADR-001`–`004`, `007`–`009`) — the record of *why* the architecture is shaped the way it is, for the
decisions significant enough to require one.

## Execution Lifecycle

One Goal drives all nine constitutional stages in a fixed order — Intent → Engineering → Context →
Planning → Actuation → Validation → Recovery → Reflection → Knowledge — through
`nexus_workflows.spine.ConstitutionalPipeline`. See:
- [`docs/v2/01_ARCHITECTURE.md`](../v2/01_ARCHITECTURE.md) — overall platform architecture and layer responsibilities
- [`docs/v2/18_EXECUTION_GRAPH.md`](../v2/18_EXECUTION_GRAPH.md) — the operational topology a Plan compiles into
- [`docs/internals/WALKTHROUGH-v2.md`](../internals/WALKTHROUGH-v2.md) §5–7 — the pipeline in code, plus a worked example of the exact cross-goal identity defect RC2 found and fixed

## Runtime

- [`docs/v2/runtime/00_RUNTIME_OVERVIEW.md`](../v2/runtime/00_RUNTIME_OVERVIEW.md) and the rest of
  `docs/v2/runtime/` — the frozen design (matching, allocation, adapters, lifecycle, streaming,
  cancellation, timeout, error/progress/artifact models, observability, security, governance)
- [`docs/runtime/README.md`](../runtime/README.md) — the as-built engineering record per runtime
  subsystem (recovery, validation, knowledge, reflection, workflows, adapters, execution), and how it
  relates to the design docs above

## Scheduler

[`docs/v2/P16_AUTONOMY_AND_SCHEDULED_OPERATIONS_REPORT.md`](../v2/P16_AUTONOMY_AND_SCHEDULED_OPERATIONS_REPORT.md) —
governed autonomy (Manual / Governed / Fully-Automatic), deterministic scheduling (one-time, delayed,
interval, cron-like), driven by an injected clock, never a wall clock. `nexus_scheduler/__main__.py`'s own
docstring documents the production entrypoint this subsystem owns.

## Memory & State

- [`docs/v2/23_EVENT_MODEL.md`](../v2/23_EVENT_MODEL.md) — the authoritative, append-only log every other model derives from
- [`docs/v2/24_STATE_MODEL.md`](../v2/24_STATE_MODEL.md) — state as a projection, never mutated in place
- [`docs/v2/25_CHECKPOINT_MODEL.md`](../v2/25_CHECKPOINT_MODEL.md) — derived snapshots over the event log
- [`docs/v2/knowledge/`](../v2/knowledge/) and [`docs/runtime/knowledge/`](../runtime/knowledge/) — durable operational memory, design and as-built

## Governance

- [`docs/v2/12_GOVERNANCE.md`](../v2/12_GOVERNANCE.md) — the governance model overall
- [`docs/v2/20_POLICY_ENGINE.md`](../v2/20_POLICY_ENGINE.md) — the Policy Engine's declarative rule model, precedence, and fail-closed default

## Replay & Recovery

- [`docs/v2/19_RECOVERY.md`](../v2/19_RECOVERY.md) and [`docs/runtime/recovery/RECOVERY_ENGINE.md`](../runtime/recovery/RECOVERY_ENGINE.md) —
  Recovery: the decision layer between a Validation judgment and what happens next
- [`docs/internals/WALKTHROUGH-v2.md`](../internals/WALKTHROUGH-v2.md) §6 — why replay and restart are
  exact (the (identifier, content) duplicate-event rule) rather than best-effort
- [`docs/v2/RC1_PRODUCTIZATION_REPORT.md`](../v2/RC1_PRODUCTIZATION_REPORT.md) §6 and
  [`docs/v2/RC2_EXECUTION_IDENTITY_REPORT.md`](../v2/RC2_EXECUTION_IDENTITY_REPORT.md) — measured
  replay/restart performance, and the regression evidence that concurrent goals replay independently

## Validation

[`docs/v2/14_VALIDATION.md`](../v2/14_VALIDATION.md) and
[`docs/runtime/validation/VALIDATION_ENGINE.md`](../runtime/validation/VALIDATION_ENGINE.md) — judging
execution outcomes from deterministic evidence, never the runtime's self-report (INV-20).

## Operations

[`docs/v2/P15_APPROVAL_EXCHANGE_AND_OPERATIONS_REPORT.md`](../v2/P15_APPROVAL_EXCHANGE_AND_OPERATIONS_REPORT.md) —
the read-only observation surface (`nexus_operations`): active sessions, health, replay/restart
inventories, diagnostics. Operating the platform day-to-day is
[`docs/v2/OPERATOR_GUIDE.md`](../v2/OPERATOR_GUIDE.md)'s job, not this portal's — go there directly for
that.

## Approval Exchange

[`docs/v2/human_interaction/05_APPROVALS.md`](../v2/human_interaction/05_APPROVALS.md) and the same P15
report above — how a gated node pauses execution and how `nexus_approval.ApprovalExchange` completes the
governance loop on an operator's decision.

---

Every document this portal links to already existed before this page was written; nothing here is new
architecture, a new claim, or a restatement that could drift from its source. If a linked document and
this portal ever disagree, the linked document is correct — file it as a documentation bug.
