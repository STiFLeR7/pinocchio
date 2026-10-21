# Context Engineering

Status: Target Architecture

---

# Purpose

Context Engineering is responsible for transforming incomplete operator intent into complete operational understanding.

It is the process of discovering, selecting, validating, enriching, organizing, and packaging all information required for successful execution.

Context Engineering is independent of execution.

Its responsibility is understanding.

---

# Why Context Engineering Exists

Execution quality is directly limited by context quality.

Most AI systems depend on manually assembled prompts.

Nexus instead constructs operational context automatically.

Rather than asking

> "What prompt should be sent?"

Nexus asks

> "What information is required to accomplish this goal successfully?"

This distinction defines Context Engineering.

---

# Design Principles

## Goal Driven

Context always begins with a Goal.

Never with a prompt.

---

## Domain Agnostic

Context Engineering should work for any operational domain.

Examples

- Software Engineering
- Research
- Writing
- Business Operations
- Personal Productivity
- Architecture
- Documentation
- Planning
- Analysis
- Education

The process remains identical.

Only context sources change.

---

## Runtime Independent

Context should never depend on Claude, Gemini, Nexus Agent, or any future runtime.

Context exists before runtime selection.

---

## Minimal Complete Context

Context should be sufficient.

Not excessive.

The objective is to provide exactly enough information to perform work reliably.

---

## Continuously Enriched

Context is never static.

As execution progresses, new information may become available.

Context Packages should evolve.

---

# Context Lifecycle

```

```
Goal

↓

Discover

↓

Collect

↓

Validate

↓

Enrich

↓

Organize

↓

Package

↓

Context Package
```

---

# Context Sources

Context Engineering may gather information from many sources.

Examples include

## Workspace

- Repository
- Filesystem
- Google Drive
- Notion
- Email
- Calendar
- Slack
- Discord
- Jira
- Linear

---

## Knowledge

- Previous executions
- Existing documentation
- Research
- Knowledge Base
- ADRs
- Operational history

---

## Operator

- Current goal
- Constraints
- Priorities
- Preferences
- Deadlines

---

## Runtime

- Available capabilities
- Available tools
- Cost
- Time limits

---

## Environment

- Active workflows
- Running executions
- Current branch
- Existing TODOs
- Open approvals
- Current operational state

---

# Context Categories

A Context Package is composed of multiple categories.

---

## Goal Context

Defines

- objective
- desired outcome
- success definition

---

## Domain Context

Defines

- operational domain
- terminology
- knowledge requirements
- standards

---

## Workspace Context

Defines

- operational environment
- repositories
- files
- documents
- communication channels

---

## Historical Context

Defines

- previous work
- previous failures
- previous executions
- previous decisions

---

## Operational Context

Defines

- current state
- running workflows
- open tasks
- priorities
- dependencies

---

## Constraint Context

Defines

- governance
- security
- deadlines
- approvals
- quality expectations
- budgets

---

## Resource Context

Defines

- available runtimes
- available tools
- available knowledge
- available skills

---

## Execution Context

Defines

- validation requirements
- expected outputs
- execution assumptions
- dependencies

---

# Context Discovery

Context Engineering should actively discover missing information.

Questions include

- What already exists?
- What information is missing?
- What assumptions are being made?
- What dependencies exist?
- What evidence will eventually be required?

Context discovery reduces ambiguity.

---

# Context Validation

Every Context Package should be evaluated before planning.

Validation includes

Completeness

Consistency

Availability

Freshness

Authorization

Quality

Missing or conflicting context should be identified before planning begins.

---

# Context Enrichment

Raw context is rarely sufficient.

Context Engineering may enrich information by

- discovering related documents
- locating previous work
- identifying dependencies
- finding architectural decisions
- collecting supporting evidence
- organizing information

The objective is operational understanding.

Not information collection.

---

# Context Packaging

The output of Context Engineering is a Context Package.

A Context Package contains

Goal

Context Categories

Constraints

Resources

Supporting Artifacts

References

Confidence

Known Unknowns

Validation Status

The package becomes the input to Planning.

---

# Domain Examples

## Software Engineering

Context may include

- repository
- architecture
- ADRs
- open issues
- coding conventions
- previous implementations
- tests

---

## Research

Context may include

- research question
- previous findings
- trusted sources
- search strategy
- knowledge gaps

---

## Personal Productivity

Context may include

- calendar
- existing tasks
- priorities
- deadlines
- available time
- commitments

---

## Documentation

Context may include

- existing documentation
- architecture
- audience
- style guides
- previous revisions

---

## Business Operations

Context may include

- stakeholders
- current projects
- objectives
- KPIs
- deadlines
- dependencies

---

# Architectural Boundaries

Context Engineering

✓ discovers context

✓ validates context

✓ enriches context

✓ organizes context

✓ packages context

Context Engineering never

✗ creates execution plans

✗ selects runtimes

✗ performs execution

✗ validates execution

✗ performs recovery

Those responsibilities belong to later capability layers.

---

# Future Evolution

Future versions may introduce

- adaptive context generation
- context scoring
- automatic context pruning
- semantic context graphs
- organization-wide context sharing
- predictive context discovery

These capabilities should preserve the principles defined in this document.

---

# North Star

Context Engineering transforms incomplete operator intent into complete operational understanding.

Every capability that follows depends on the quality of the Context Package.

Execution quality begins with context quality.