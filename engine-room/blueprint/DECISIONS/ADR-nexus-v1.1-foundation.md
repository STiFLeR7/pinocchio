# ADR-nexus-v1.1-foundation: Nexus Evolution Design (Prototype → Experimental → Pilot)

Date: 2026-06-24
Status: Proposed (design — implementation gated)
Release line: v1.1.0 "Containment" · Track H
Related: ADR-nexus-reality-audit (v1.0.1, Accepted), ADR-v1.0.1-alignment-release,
`H-1-nexus-master-design.md` (+ capability/lifecycle/recovery/tooling sub-designs),
`R-05-shared-resolution.md`
Supersedes: none (builds on the accepted Prototype classification)

---

## Context

`ADR-nexus-reality-audit` (Accepted, v1.0.1) classified Nexus a **Prototype**: real persistence,
governance, and file/command tool execution, but with an in-prod `AsyncMock`, decorative hardcoded
planning, simulated search, always-`0` exit status, a no-op-and-uninvoked `terminate()`, and no resume
(`nexus.py:7,76-86,147-151,186-211,284-289,301-314`). v1.1.0 Track H is chartered to evolve Nexus to
**Experimental** then **Pilot** — design first, implementation separately gated — without touching the
runtime-abstraction, governance, approval, scheduler, memory, or event architectures.

## Decision

Adopt the H-1 design as the foundation for Nexus evolution, structured as **four pillars** mapped to
two evidence-defined promotion gates:

- **Pillar A — Honest decision-making** (remove prod mock; goal-derived advisory planning;
  schema-validated structured tool-calls; real exit status) → **Experimental**.
- **Pillar B — Real tools** (`SearchProvider` port with a real provider; canned search demoted to a
  test double; file/command tools converge on the sandbox boundary) → **Experimental** (search) /
  **Pilot** (files).
- **Pillar C — Lifecycle safety** (explicit state machine; cooperative DB-observable cancellation with
  `terminate()` wired into the orchestrator + timeout path; `TIMED_OUT`/`FAILED` distinct from
  `COMPLETED`; fail-fast init; configurable step budget) → **Pilot**.
- **Pillar D — Recoverability** (`resume_goal` reconstructs trajectory from `agent_steps` + latest
  checkpoint, mirroring `resume_research_run`/`resume_briefing_run`; checkpoints stay per-step,
  `agent_steps` is the trajectory system of record) → **Pilot**.

**Promotion gates (evidence-bound):**
- **Prototype → Experimental:** no simulation in the prod path; real exit status; real search;
  structured tool-calls; goal-derived plan; real-LLM-branch tests.
- **Experimental → Pilot:** the above **plus** wired+tested cancellation, working+tested resume,
  R-05 file-tool confinement, fail-fast init, configurable budget, and one audited real governed run.

**Boundaries:** no schema redesign (resume is a read over existing data; any status-enum addition is
additive and decided at the implementation AP); no new tools, model backends, agent types, or events
beyond what a listed gap requires; the `SCHEDULER_JOB_*` taxonomy is **not** overloaded; R-05 is owned by
Track S and consumed by Track H (single resolution).

## Consequences

**Positive**
- Nexus becomes *honest first* (Experimental) then *lifecycle-safe + contained* (Pilot), each step
  backed by AP-105 evidence and gated for review.
- Pure reuse of existing primitives (agent_steps, checkpoints, audit ledger, governance, sandbox,
  resume idiom) — minimal architectural surface, no hidden coupling.

**Negative / accepted**
- Until implementation lands, Nexus remains a Prototype; the classification does not change on design alone.
- Full **Production Ready** status is explicitly **not** a v1.1.0 goal (deferred).
- Real search introduces network I/O whose egress is governed by Track S policy (cross-track dependency,
  R-05 / containment design) — accepted and documented, not hidden.

**Implementation sequencing (gated, not authorized here)**
H-2 honesty fixes (Pillar A, P0) → H-3 real search + planning (Pillar A/B, P0/P1) → H-4 lifecycle +
resume (Pillars C/D, P1) → H-5 hardening + R-05 file confinement + test depth (with Track S). Each is a
separate, separately-approved AP.

## Status

**Proposed.** Design artifacts complete and submitted for review. No code, no migration, no commit of
implementation. Awaiting acceptance before any H-2+ implementation AP begins.
