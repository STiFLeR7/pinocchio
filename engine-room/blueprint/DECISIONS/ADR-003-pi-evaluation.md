# ADR-003: Pi Evaluation Requirement and Sequencing

Date: 2026-06-19
Status: Closed — Rejected (Option C)

---

## Context

Multiple Nexus documents (00_BRIEF, 03_AGENT_DESIGN, 05_CRITICAL_CONSTRAINTS, 06_DEVELOPMENT_PHASES, 07_REFERENCES, RULES) mandate evaluation of:

```
https://github.com/earendil-works/pi
```

The constraint is explicit:

> Before implementing orchestration primitives, evaluate Pi.
> Do not rebuild capabilities without evaluation.

However, the documented Phase 8 placement creates a sequencing risk: Phase 1 (Core Infrastructure) builds the Workflow Orchestrator before Pi is evaluated.

---

## Problem

**Sequencing Conflict:**

```
Phase 0  — Foundation (No orchestration)
Phase 1  — Core Infrastructure (Builds Workflow Orchestrator ← CONFLICT)
...
Phase 8  — Pi Evaluation
```

If Pi is evaluated in Phase 8 and found to be a good fit, the Phase 1 Workflow Orchestrator may need to be replaced — creating significant rework.

**Constraint 25 is unambiguous:**

> Before implementing orchestration primitives:
> Evaluate https://github.com/earendil-works/pi

---

## Decision

**Proposed Resolution:**

Run Pi evaluation as a **Phase 0 parallel track**, not Phase 8.

Pi evaluation findings must be available before Phase 1 design begins.

**Evaluation Questions:**

1. Can Pi provide workflow execution?
2. Can Pi provide state management?
3. Can Pi provide agent orchestration?
4. Can Pi provide task coordination?
5. Can Pi provide scheduling primitives?
6. Can Pi provide failure recovery?
7. Can Pi provide persistence?
8. Can Pi provide observability?

**Decision Outcomes:**

| Option | Description | Consequence |
|---|---|---|
| Option A | Adopt Pi as orchestration layer | Phase 1 design changes significantly |
| Option B | Partial integration | Selective adoption, custom gaps |
| Option C | Reject | Proceed with custom orchestrator |

---

## Required Action

1. Clone https://github.com/earendil-works/pi
2. Analyze architecture, APIs, and state model
3. Map Pi capabilities against Nexus requirements
4. Document findings in `blueprint/references/pi-evaluation.md`
5. Make a decision before Phase 1 begins

---

## Status

**Closed — Rejected**

Evaluation was conducted on 2026-06-19.

### Decision Outcome

Option C was selected: Proceed with a custom Python-based orchestrator, utilizing the robust foundational stack established in Phase 0.

### Justification

1. **Tech Stack Alignment**: Pi is TypeScript-based. Integrating it into our Python control plane introduces language-bridge overhead, double container configs, and violates ADR-006.
2. **Missing Primitives**: Pi does not provide native relational database mappings (SQLAlchemy), multi-agent event routing, task prioritization, cron scheduling (APScheduler), or Discord-based approval authorization gates.
3. **Architectural Overhead**: Adapting Pi to fit Nexus's control plane model requires writing more interface code than implementing a lightweight, Python-native state machine.

We will proceed by implementing the Event Gateway, Task Engine, and Workflow Orchestrator natively in Python during Phase 1.

---

## References

- [docs/00_BRIEF.md](../../docs/00_BRIEF.md) — Pi Evaluation Requirement
- [docs/03_AGENT_DESIGN.md](../../docs/03_AGENT_DESIGN.md) — Pi Integration Evaluation
- [docs/05_CRITICAL_CONSTRAINTS.md](../../docs/05_CRITICAL_CONSTRAINTS.md) — Constraint 25
- [docs/06_DEVELOPMENT_PHASES.md](../../docs/06_DEVELOPMENT_PHASES.md) — Phase 8
- [docs/07_NEXUS_AGENT.md](../../docs/07_NEXUS_AGENT.md) — Reference 1
- [docs/RULES.md](../../docs/RULES.md) — Pi Integration Consideration
