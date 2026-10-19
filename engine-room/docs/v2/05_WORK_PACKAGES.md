# Work Packages

Status: Target Architecture

---

# Purpose

Work Packages are the fundamental execution unit of Nexus.

Goals represent desired outcomes.

Plans describe approaches.

Work Packages represent executable operational work.

Every execution performed by Nexus begins with one or more Work Packages.

Runtimes never receive Goals.

Runtimes receive Work Packages.

---

# Why Work Packages Exist

Operators think in goals.

Execution engines think in actions.

Work Packages bridge those two worlds.

Instead of passing raw requests directly to execution engines, Nexus constructs structured operational packages that contain everything required for reliable execution.

---

# Design Principles

## Atomic

A Work Package should represent one independently executable objective.

It should never contain multiple unrelated objectives.

---

## Self Describing

Every Work Package should explain

- what must be done
- why it exists
- expected outcome
- completion criteria

without requiring the original operator request.

---

## Context Complete

A Work Package should include every operational context required for execution.

Execution engines should not discover missing information.

---

## Runtime Independent

A Work Package should never contain runtime-specific instructions.

Claude Code.

Gemini.

Nexus Agent.

Future runtimes.

All consume the same Work Package.

---

## Observable

Every Work Package should produce measurable progress.

Execution should never become invisible.

---

## Recoverable

Execution should resume from the latest Work Package state.

Never from the original Goal.

---

# Lifecycle

```
Goal

↓

Plan

↓

Work Package

↓

Execution

↓

Evidence

↓

Completed
```

---

# Structure

Every Work Package contains

## Identity

- Identifier
- Parent Goal
- Parent Plan
- Priority

---

## Objective

Defines

- desired outcome
- operational purpose

---

## Context

Contains

- Context Package
- supporting artifacts
- references
- dependencies

---

## Constraints

Defines

- governance
- approvals
- deadlines
- budgets
- quality requirements

---

## Resources

Defines available resources

Examples

- Claude Code
- Gemini
- GitHub
- Filesystem
- Calendar
- Search
- Memory

Resources describe availability.

Not selection.

---

## Skills

References required Skills.

Examples

- Research

- Bug Resolution

- Documentation

- Architecture Review

- Root Cause Analysis

Skills define capability.

---

## Inputs

Required information.

Examples

- Repository

- Documents

- Existing TODOs

- Research Papers

- ADRs

- Calendar Events

---

## Outputs

Expected deliverables.

Examples

- Report

- Source Code

- Presentation

- Documentation

- Summary

- Pull Request

---

## Evidence

Defines how completion is verified.

Examples

- tests passed

- document created

- report generated

- artifact published

- review completed

---

## Completion Criteria

Defines success.

Completion should never depend upon runtime confidence.

---

# Relationships

Work Packages may depend on one another.

Example

```
Research

↓

Architecture

↓

Implementation

↓

Validation

↓

Documentation
```

Dependencies define execution ordering.

---

# Granularity

Work Packages should be

Large enough to represent meaningful work.

Small enough to execute independently.

Poor example

```
Build Nexus
```

Good example

```
Design Context Engineering

Implement Context Loader

Validate Context Assembly

Generate Documentation
```

---

# Composition

Multiple Work Packages may compose larger operational plans.

```
Goal

↓

Plan

├── Research

├── Analysis

├── Draft

├── Review

└── Publish
```

Plans own Work Packages.

Work Packages never own Plans.

---

# Status

Typical lifecycle

```
Created

↓

Ready

↓

Executing

↓

Paused

↓

Completed
```

Failure states

```
Blocked

Cancelled

Failed

Expired
```

---

# Checkpoints

Work Packages support checkpoints.

Examples

Planning Complete

Context Ready

Execution Started

Execution Paused

Execution Resumed

Validation Complete

Checkpointing enables recovery.

---

# Observability

Every Work Package should expose

- current state

- progress

- elapsed time

- active runtime

- evidence collected

- artifacts generated

Observability supports supervision.

---

# Architectural Boundaries

Work Packages

✓ package work

✓ package context

✓ package constraints

✓ package expected outputs

✓ package evidence requirements

Work Packages never

✗ perform execution

✗ create plans

✗ select runtimes

✗ validate evidence

Those responsibilities belong elsewhere.

---

# Future Evolution

Future versions may support

- nested Work Packages

- reusable templates

- dynamic decomposition

- distributed execution

- collaborative ownership

- adaptive checkpointing

These additions should preserve the architectural principles defined in this document.

---

# North Star

A Work Package is the smallest complete operational unit within Nexus.

It contains everything required for reliable execution while remaining independent of any execution technology.

Execution engines receive Work Packages.

Operational intelligence creates them.