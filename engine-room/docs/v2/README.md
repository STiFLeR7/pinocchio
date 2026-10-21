# Nexus v2

> **Operational Intelligence Platform for Human-Governed AI Execution**

**Status:** Released — `v2.0.0` ("Constitutional Spine"), tagged and merged to `master`.  
**Version:** v2.0.0  
**Audience:** Engineers, Architects, AI Runtime Developers, Contributors

> The documents in this directory were written as the **target architecture** before implementation
> began (Phase 0). Implementation followed them through P1–P17, RC1, and RC2, and the platform is now
> released as `v2.0.0` — see `docs/v2/V1_RELEASE_READINESS_REPORT.md` and
> `docs/v2/V2_RELEASE_EXECUTION_REPORT.md` for the release evidence, and
> `docs/internals/WALKTHROUGH-v2.md` for a code-level tour of the shipped implementation. This directory
> remains the authoritative design record; treat it as describing the platform as built, not as a
> not-yet-built proposal.
>
> **Looking for one page that indexes every subsystem instead of reading these files one at a time?**
> See [`docs/architecture/README.md`](../architecture/README.md), the architecture portal.

---

## Overview

Nexus is evolving from an AI Orchestration Control Plane into an **Operational Intelligence Platform**.

The first generation of Nexus established the operational foundation:

- Communication
- Governance
- Memory
- Runtime Management
- Scheduling
- Event Processing
- Agent Execution
- Human Approval
- Observability

These capabilities created a deterministic and governed execution platform.

The next generation focuses on something fundamentally different.

Rather than improving execution, Nexus now focuses on understanding work before execution begins.

---

## Vision

Execution is becoming commoditized.

Every month, new agent frameworks, coding assistants, research agents, planning agents, and AI runtimes become available.

The competitive advantage is no longer execution.

The competitive advantage is operational intelligence.

Nexus exists to provide that intelligence.

It understands operator intent, constructs operational context, plans work, selects capabilities, supervises execution, validates outcomes, learns from results, and continuously improves future operations.

Execution becomes only one capability of the platform.

---

## Evolution

### Nexus v1

Nexus v1 established the execution foundation.

Primary capabilities included:

- Runtime Registry
- Workflow Orchestration
- Human Governance
- Approval System
- Event Gateway
- Communication
- Scheduling
- Persistent Memory
- Agent Runtime
- Research
- Operational Briefings

The platform coordinates execution reliably and transparently.

---

### Nexus Next

The next architecture introduces a higher layer.

Instead of only orchestrating execution, Nexus begins orchestrating operational intelligence.

New capability areas include:

- Intent Resolution
- Context Engineering
- Planning
- Operational Skills
- Execution Strategies
- Supervision
- Reflection
- Knowledge
- Continuous Learning

Execution becomes one stage inside a much larger operational lifecycle.

---

## Design Philosophy

Nexus is built around several architectural principles.

### Goals instead of Commands

Operators express goals.

Nexus determines how those goals should be achieved.

---

### Context before Execution

Execution should never begin without sufficient context.

The platform assembles operational context before selecting tools or runtimes.

---

### Skills instead of Prompts

Operational knowledge is represented as reusable Skills.

Skills describe procedures, requirements, validation, and expected outcomes.

They are independent of any particular AI model.

---

### Planning before Orchestration

Planning decides what work should happen.

Orchestration decides how work is coordinated.

Execution performs the work.

These responsibilities remain independent.

---

### Evidence instead of Claims

Successful execution is determined through observable evidence.

Completion is never based solely on runtime responses.

---

### Learning instead of History

Execution history is useful.

Operational learning is valuable.

Nexus stores patterns, reflections, failures, and successful strategies to improve future planning.

---

## Capability Layers

The platform is organized into capability layers.

```
Operator
    │
    ▼
Intent Resolution
    │
    ▼
Context Engineering
    │
    ▼
Planning
    │
    ▼
Execution Strategy
    │
    ▼
Skill Selection
    │
    ▼
Orchestration
    │
    ▼
Execution
    │
    ▼
Supervision
    │
    ▼
Validation
    │
    ▼
Reflection
    │
    ▼
Knowledge
```

Every layer has a single responsibility.

No layer should assume responsibilities belonging to another.

---

## Architectural Goals

The next architecture is designed to be:

- Goal Driven
- Domain Agnostic
- Runtime Independent
- Observable
- Recoverable
- Extensible
- Governed
- Context Aware
- Skill Based
- Evidence Driven

---

## Document Structure

This directory contains the target architecture for the next generation of
Nexus. The pipeline documents (00–26) describe the 13 capability layers and the
cross-cutting substrate; the reconciliation documents (99, REVIEW, MIGRATION,
CONSISTENCY) finalize the Phase 0 baseline.

| Document | Purpose |
|----------|---------|
| `00_VISION.md` | Long-term vision and platform philosophy |
| `01_ARCHITECTURE.md` | Overall platform architecture and layer responsibilities |
| `02_OBJECT_MODEL.md` | Canonical operational objects and ownership |
| `03_CONTEXT_ENGINEERING.md` | Context Engineering subsystem |
| `04_PLANNING.md` | Goal decomposition and planning |
| `05_WORK_PACKAGES.md` | Work Package specification |
| `06_SKILLS.md` | Operational Skill architecture |
| `07_ORCHESTRATION.md` | Coordination architecture |
| `08_EXECUTION.md` | Execution architecture |
| `09_SUPERVISION.md` | Observation and operational health |
| `10_KNOWLEDGE.md` | Operational knowledge architecture |
| `11_HARNESS.md` | Integration boundary (Harness) architecture |
| `12_GOVERNANCE.md` | Governance model |
| `13_EXECUTION_STRATEGY.md` | Execution Strategy (coordination behavior) |
| `14_VALIDATION.md` | Evidence-based validation |
| `15_RUNTIME_MODEL.md` | Runtime abstraction (a Harness category) |
| `16_INTENT_RESOLUTION.md` | Intent Resolution (the first capability layer) |
| `17_ARTIFACT_MODEL.md` | Artifact model |
| `18_EXECUTION_GRAPH.md` | Execution Graph (operational topology) |
| `19_RECOVERY.md` | Recovery architecture |
| `20_POLICY_ENGINE.md` | Policy evaluation engine |
| `21_CAPABILITY_MODEL.md` | Capability model |
| `22_RESOURCE_MODEL.md` | Resource model |
| `23_EVENT_MODEL.md` | Event model (authoritative log) |
| `24_STATE_MODEL.md` | State model (projection) |
| `25_CHECKPOINT_MODEL.md` | Checkpoint model (derived snapshots) |
| `26_REFLECTION.md` | Reflection architecture |
| `99_ARCHITECTURAL_INVARIANTS.md` | Permanent architectural guardrails (INV-xx) |
| `ARCHITECTURE_REVIEW.md` | Phase 0 ARB record and implementation-readiness verdict |
| `MIGRATION_FROM_V1.md` | Conceptual migration from Nexus v1 to v2 |
| `CONSISTENCY_REPORT.md` | Phase 0 consistency audit and corrections |

### Related Phase 0 Artifacts

| Location | Purpose |
|----------|---------|
| `adr/ADR-001..004` | Ratified foundational Architecture Decision Records |
| `contracts/` | Frozen canonical logical contracts (one per object) |
| `blueprint/v2/` | Implementation phases, Action Points, roadmap, risks, testing |

---

## Design Status

These documents describe the architecture **as designed and, as of `v2.0.0`, as released.**

They were written independently of any implementation (Phase 0), so that implementation would be built
*against* them rather than the reverse. Implementation followed incrementally across P1–P17 and two
hardening passes (RC1, RC2), each verified against the principles defined here rather than revising them
to match convenience — see `docs/v2/ADR_RATIFICATION_REPORT.md` for the small number of places where
implementation experience did require a documented, reviewed correction (e.g. ADR-009).

---

## North Star

Nexus is not an AI assistant.

Nexus is not an agent framework.

Nexus is not an execution engine.

Nexus is an Operational Intelligence Platform that continuously transforms operator intent into reliable, governed, observable, recoverable, and continuously improving execution.