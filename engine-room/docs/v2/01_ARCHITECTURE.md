# Nexus Architecture

Status: Target Architecture (Phase 0 reconciled)

> **Phase 0 reconciliation note.** Per `adr/ADR-003`, the first capability layer
> is canonically named **Intent Resolution** (formerly "Executive Intelligence,"
> now a deprecated alias). The canonical object definitions are frozen in
> `contracts/` and the permanent rules in `99_ARCHITECTURAL_INVARIANTS.md`.

---

# Purpose

This document defines the architectural structure of Nexus.

It establishes the responsibilities, boundaries, capability layers, and operational lifecycle that govern every subsystem within the platform.

This document intentionally avoids implementation details.

Instead, it defines how the platform should think about work.

Every future implementation must preserve these architectural boundaries.

---

# What is Nexus?

Nexus is an Operational Intelligence Platform.

It exists to transform operator goals into reliable, governed, observable, recoverable, and continuously improving execution.

Execution is only one capability of the platform.

The platform itself is responsible for understanding work.

---

# Architectural Philosophy

Nexus separates operational intelligence from execution.

Execution engines are replaceable.

Operational intelligence is not.

Instead of building around AI models, Nexus is built around operational capabilities.

This allows the platform to evolve independently from any particular runtime.

---

# Capability Architecture

The platform is organized as a sequence of capability layers.

Each layer has exactly one responsibility.

Each layer produces outputs consumed by the next layer.

```

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
                  Planning Engine
                        │
                        ▼
                Execution Strategy
                        │
                        ▼
                  Skill Selection
                        │
                        ▼
                  Work Packaging
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

---

# Layer Responsibilities

## Intent Resolution

Responsible for understanding operator intent.

Inputs

- Goals
- Constraints
- Requests

Outputs

- Operational Goal

Responsibilities

- understand intent
- classify work
- identify complexity
- identify objectives
- identify operational scope

Intent Resolution never performs execution.

---

## Context Engineering

Responsible for building operational understanding.

Inputs

- Goal

Outputs

- Context Package

Responsibilities

- collect context
- enrich context
- validate completeness
- identify dependencies
- organize information

Context Engineering never performs planning.

---

## Planning Engine

Responsible for determining how work should be performed.

Inputs

- Goal
- Context Package

Outputs

- Plan
- Work Packages
- Execution Graph

Planning transforms understanding into executable work.

---

## Execution Strategy

Responsible for determining execution behavior.

Examples

- Sequential
- Parallel
- Human approval
- Multi-runtime
- Validation-first
- Research-first

Execution Strategy determines coordination.

It never executes work.

---

## Skill Selection

Responsible for selecting operational capabilities.

Skills are reusable operational procedures.

Examples

- Bug Resolution
- Research
- Documentation
- Planning
- Architecture Review
- Root Cause Analysis

Skill Selection determines capability.

Not implementation.

---

## Work Packaging

Responsible for creating execution-ready packages.

Each package contains

- objective
- context
- constraints
- resources
- required skills
- validation strategy
- expected outputs

Every runtime receives Work Packages.

Never raw operator requests.

---

## Orchestration

Responsible for coordinating work.

Responsibilities

- scheduling
- delegation
- dependency management
- approvals
- checkpointing
- coordination
- retries
- synchronization

Orchestration coordinates.

It does not understand work.

---

## Execution

Responsible for performing work.

Execution may use

- Claude Code
- Gemini CLI
- Nexus Agent
- Future runtimes
- Human operators

Execution is replaceable.

Execution never owns operational intelligence.

---

## Supervision

Responsible for observing execution.

Responsibilities

- monitor progress
- detect failures
- suspend execution
- resume execution
- escalate
- collect telemetry

Supervision observes.

It does not execute.

---

## Validation

Responsible for determining completion.

Validation uses evidence.

Never runtime confidence.

Examples

- tests passed
- report generated
- artifact created
- deployment verified
- research completed

---

## Reflection

Responsible for understanding execution outcomes.

Reflection asks

- What succeeded?
- What failed?
- Why?
- What should improve?

Reflection improves future operations.

---

## Knowledge

Responsible for persistent operational intelligence.

Knowledge stores

- operational patterns
- execution history
- reusable context
- successful strategies
- failure patterns
- validated evidence

Knowledge improves future planning.

---

# Dependency Direction

The platform follows one-way dependency flow.

```

```
Intent Resolution

↓

Context Engineering

↓

Planning

↓

Execution Strategy

↓

Skill Selection

↓

Work Packaging

↓

Orchestration

↓

Execution

↓

Supervision

↓

Validation

↓

Reflection

↓

Knowledge
```

Higher layers understand work.

Lower layers execute work.

Lower layers never influence higher-level architectural decisions.

---

# Architectural Rules

## Rule 1

Execution never performs planning.

---

## Rule 2

Planning never performs execution.

---

## Rule 3

Context Engineering never owns knowledge.

It consumes knowledge.

---

## Rule 4

Knowledge never performs execution.

---

## Rule 5

Validation never trusts runtime responses.

Validation uses independently observable evidence.

---

## Rule 6

Skills describe operational capability.

They never describe runtime implementation.

---

## Rule 7

Goals remain implementation independent.

Goals describe outcomes.

Never procedures.

---

## Rule 8

Every execution must be observable.

---

## Rule 9

Every operational decision should be explainable.

---

## Rule 10

Every subsystem should have one primary responsibility.

---

# Cross-Cutting Capabilities

Every capability layer interacts with shared platform services.

These include

- Governance
- Memory
- Communication
- Scheduler
- Event Gateway
- Runtime Registry
- Observability
- Policy Engine
- Audit
- Security

These services remain infrastructure.

They do not own operational intelligence.

---

# Operational Lifecycle

Every operational request follows the same lifecycle.

```

```
Goal

↓

Understand

↓

Context

↓

Plan

↓

Select Skills

↓

Create Work Packages

↓

Determine Execution Strategy

↓

Orchestrate

↓

Execute

↓

Observe

↓

Validate

↓

Reflect

↓

Persist Knowledge
```

Every execution follows this lifecycle regardless of domain.

---

# Architectural Boundaries

| Capability | Responsible Layer |
|------------|-------------------|
| Understand Goals | Intent Resolution |
| Build Context | Context Engineering |
| Create Plans | Planning |
| Select Skills | Skill System |
| Package Work | Work Packaging |
| Coordinate Work | Orchestration |
| Execute Work | Execution |
| Observe Work | Supervision |
| Validate Outcomes | Validation |
| Learn | Knowledge |

Responsibilities should never overlap.

---

# Design Goals

The architecture should remain

- Goal Driven
- Context Aware
- Runtime Independent
- Domain Agnostic
- Observable
- Recoverable
- Governed
- Explainable
- Extensible
- Evidence Driven

---

# North Star

Nexus is not an execution framework.

Nexus is the operational layer that exists above execution.

Its responsibility is to continuously transform goals into successful outcomes while preserving governance, context, observability, and operational intelligence.

Execution performs work.

Nexus understands work.