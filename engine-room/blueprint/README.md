# Nexus Blueprint

> The living memory system for the Nexus project.

---

## Purpose

The `blueprint/` directory is the **single source of truth for project execution**.

Every implementation decision, architectural change, phase status, action point, bug, and resolution is recorded here.

**Documentation is not optional. Documentation is part of implementation.**

---

## Structure

```
blueprint/
├── README.md                  # This file
├── STATUS.md                  # Current project status (authoritative)
├── ROADMAP.md                 # Reconstructed history + forward direction
├── GAPS_AND_RISKS.md          # Identified gaps, risks, and open questions
├── DECISIONS/                 # 21 Architectural Decision Records (ADR-001…ADR-011 +
│                              #   runtime/scheduler/command-bus/phase ADRs) — see directory
├── onboarding/                # Accepted v1.0.0 onboarding audit (01…15) — reality source
├── implementations/           # Per-release implementation reports (incl. v1.0.1/)
├── architecture/              # Architecture & design records
├── reports/                   # Reviews, gap analyses, runtime/Nexus classifications
├── action-points/             # Phase action-point breakdowns
├── phases/                    # Phase-by-phase implementation memory
└── references/                # Evaluated external references (Pi, Nexus, CLIs)
```

> The `DECISIONS/` directory currently holds **21 ADRs** (the original landing page listed only three).
> Treat the directory itself as the ADR index. For current subsystem status, see
> `implementations/v1.0.1/architecture-status-summary.md`.

---

## How to Use

### Recording a Decision

Create or update a file under `blueprint/DECISIONS/ADR-NNN-title.md`.

Use the ADR template:

```markdown
# ADR-NNN: Title

Date: YYYY-MM-DD
Status: Proposed | Accepted | Superseded
Supersedes: ADR-NNN (if applicable)

## Context
What situation prompted this decision?

## Decision
What was decided?

## Consequences
What are the trade-offs and implications?
```

### Recording Phase Progress

Each phase has its own directory under `blueprint/phases/phase-N/`.

Each Action Point (AP) within a phase has its own directory.

Template for AP status:

```markdown
# AP-NNN: Title

Phase: N
Status: Not Started | In Progress | Complete | Blocked

## Objective
...

## Implementation Notes
...

## Tests
...

## Decisions Made
...

## Open Questions
...
```

### Recording a Risk or Gap

Add to `blueprint/GAPS_AND_RISKS.md`:

```markdown
## GAP-NNN: Title

Category: Missing Spec | Architectural Risk | Integration Gap | ...
Severity: Critical | High | Medium | Low
Status: Open | Resolved | Accepted

### Description
...

### Impact
...

### Resolution
...
```

---

## Memory Rules

1. **Never delete** — archive instead
2. **Always date** — every document has a date
3. **Always link** — cross-reference related APs and decisions
4. **Always resolve** — open questions must eventually close
5. **Always commit** — blueprint changes committed with implementation

---

## Current Status

See [STATUS.md](STATUS.md) for the current project snapshot.

See [ROADMAP.md](ROADMAP.md) for the full execution plan.

See [GAPS_AND_RISKS.md](GAPS_AND_RISKS.md) for identified risks.
