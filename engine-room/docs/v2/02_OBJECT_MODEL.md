# Nexus Object Model

Status: Target Architecture (Phase 0 reconciled — canonical)

> **Phase 0 reconciliation note.** This Object Model is the canonical
> architectural vocabulary. It is reconciled with the ratified decisions in
> `adr/ADR-001..004`; the per-object structures are frozen in `contracts/`, and
> the permanent rules in `99_ARCHITECTURAL_INVARIANTS.md`. Key reconciliations
> applied: the layer formerly called "Executive Intelligence" is canonically
> **Intent Resolution** (ADR-003); **Goal Metadata** lives inside the Goal;
> **Observation** is owned by **Supervision** (Execution emits Execution Events;
> Validation produces Evidence from Evidence Candidates); the **Execution Graph**
> is a first-class artifact **referenced by** the Plan (not nested), and the
> separate "Dependency Graph" is eliminated (dependencies are graph edges);
> **Reflection** is its own layer producing Knowledge Candidates.

---

# Purpose

The Object Model defines the fundamental concepts of Nexus.

These are architectural objects.

They are not implementations.

They are not services.

They are not database tables.

They represent the operational language of the platform.

Every subsystem within Nexus must communicate using these objects.

This creates a common vocabulary across planning, orchestration, execution, supervision, governance, memory, and knowledge.

---

# Design Principles

Objects should represent concepts rather than implementations.

Objects should remain independent of runtimes.

Objects should remain independent of storage.

Objects should remain stable across future versions.

Objects should have a single responsibility.

Objects should compose together rather than inherit behavior.

---

# Operational Hierarchy

```

```
Goal
 │
 ▼
Context Package
 │
 ▼
Plan
 │
 ▼
Work Packages
 │
 ▼
Execution Strategy
 │
 ▼
Execution Session
 │
 ▼
Evidence
 │
 ▼
Reflection
 │
 ▼
Knowledge
```

---

# Goal

A Goal represents the desired operational outcome.

Examples

- Resolve a production bug
- Research a topic
- Generate a report
- Prepare a release
- Organize TODOs
- Review architecture
- Monitor an external system
- Plan a roadmap

Goals describe outcomes.

They never describe implementation.

---

# Context Package

A Context Package represents all information required to understand a Goal.

It may contain

- historical context
- workspace context
- operational context
- constraints
- resources
- previous executions
- supporting artifacts

Every Goal should produce exactly one Context Package.

---

# Plan

A Plan describes how a Goal can be achieved.

Planning transforms Goals into executable work.

A Plan contains

- milestones
- dependencies
- priorities
- execution graph
- work packages

Plans never perform execution.

---

# Work Package

A Work Package is the smallest independently executable unit of work.

Examples

- Analyze repository
- Search literature
- Write documentation
- Review pull request
- Generate tests
- Build presentation
- Summarize meeting

Every Work Package should

- have one objective
- have defined inputs
- produce observable outputs

---

# Skill

A Skill represents reusable operational capability.

Skills are independent of AI models.

Examples

- Bug Resolution
- Research
- Architecture Review
- Documentation
- Code Review
- Planning
- Summarization
- Root Cause Analysis

A Skill defines

- requirements
- procedure
- validation
- completion criteria

Skills describe operational knowledge.

---

# Execution Strategy

Execution Strategy determines how work should execute.

Examples

Sequential

Parallel

Human approval required

Research before implementation

Validation before completion

Execution Strategy selects

- execution order
- required runtimes
- approval requirements
- recovery behavior

Execution Strategy never performs execution.

---

# Execution Session

Execution Session represents one operational execution.

It contains

- runtime
- progress
- checkpoints
- observations
- outputs
- artifacts

Execution Sessions are temporary.

Knowledge is permanent.

---

# Observation

Observations represent information collected while work executes.

Examples

Progress

Errors

Metrics

Logs

Tool usage

Checkpoint state

Observations describe execution.

They do not evaluate execution.

---

# Evidence

Evidence represents independently verifiable proof.

Examples

Successful build

Passing tests

Generated report

Created document

Validated deployment

Published artifact

Evidence determines completion.

Evidence is never generated from assumptions.

---

# Reflection

Reflection represents understanding gained after execution.

Examples

Failure patterns

Success patterns

Unexpected behavior

Optimization opportunities

Lessons learned

Reflection improves future planning.

---

# Knowledge

Knowledge represents persistent operational intelligence.

Knowledge grows over time.

Examples

Repository understanding

Research findings

Execution history

Successful strategies

Failure patterns

Operator preferences

Reusable context

Knowledge continuously improves future executions.

---

# Workspace

Workspace represents where work occurs.

Examples

Git Repository

Filesystem

Google Drive

Email

Calendar

Slack

Discord

Notion

Jira

Workspace is independent of execution.

---

# Resource

Resources represent available capabilities.

Examples

Claude Code

Gemini CLI

Nexus Agent

GitHub

Filesystem

Search

Database

Calendar

Memory

Resources enable execution.

Resources do not own execution.

---

# Constraint

Constraints define execution boundaries.

Examples

Budget

Deadline

Approval

Governance

Security

Allowed repositories

Available tools

Quality requirements

Constraints always override execution preferences.

---

# Artifact

Artifacts are outputs created during execution.

Examples

Files

Reports

Commits

Pull Requests

Presentations

Research Notes

Documentation

Artifacts become inputs to future work.

---

# Relationship Model

```

```
Goal
 │
 ▼
Context Package
 │
 ▼
Plan
 │
 ├──────────────┐
 ▼              ▼
Work Package  Work Package
 │              │
 ▼              ▼
Skill         Skill
 │              │
 └──────┬───────┘
        ▼
Execution Strategy
        ▼
Execution Session
        ▼
Observation
        ▼
Evidence
        ▼
Reflection
        ▼
Knowledge
```

---

# Object Ownership

| Object | Responsible Layer | Contract |
|---------|-------------------|----------|
| Goal | Intent Resolution | `contracts/goal.md` |
| Context Package | Context Engineering | `contracts/context_package.md` |
| Plan | Planning | `contracts/plan.md` |
| Work Package | Planning | `contracts/work_package.md` |
| Execution Strategy | Planning | `contracts/execution_strategy.md` |
| Execution Graph | Planning | `contracts/execution_graph.md` |
| Skill | Skill System | `contracts/skill.md` |
| Capability | Capability Registry | `contracts/capability.md` |
| Resource | Orchestration (allocation) | `contracts/resource.md` |
| Execution Session | Execution | — |
| Artifact | Execution (produced); Artifact Model (defined) | `contracts/artifact.md` |
| Observation | Supervision | `contracts/observation.md` |
| Evidence | Validation | (within `contracts/work_package.md`) |
| Event | Event Model (authoritative log) | `contracts/event.md` |
| Checkpoint | Checkpoint Model (derived) | `contracts/checkpoint.md` |
| Policy | Policy Engine | `contracts/policy.md` |
| Reflection | Reflection | `contracts/reflection.md` |
| Knowledge | Knowledge System | `contracts/knowledge.md` |

> The Operator request / resolved Intent that precedes a Goal is defined in
> `contracts/intent.md` (owned by Intent Resolution).

---

# Architectural Rule

Every subsystem within Nexus must consume and produce these objects.

No subsystem should introduce alternative representations for concepts already defined within this model.

The Object Model is the shared language of the platform.