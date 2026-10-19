# Skills

Status: Target Architecture

---

# Purpose

Skills represent reusable operational capabilities within Nexus.

A Skill describes how a particular type of work should be performed.

Skills are independent of AI models, runtimes, and execution technologies.

They capture operational expertise rather than implementation details.

---

# Why Skills Exist

Execution engines understand instructions.

Operators understand goals.

Skills bridge these two worlds.

Instead of repeatedly designing execution procedures, Nexus encapsulates operational knowledge into reusable Skills.

Skills become building blocks for planning and execution.

---

# Design Principles

## Capability Driven

A Skill represents a capability.

Not a tool.

Not a runtime.

Not a workflow.

---

## Runtime Independent

A Skill must never depend on Claude, Gemini, Nexus Agent, or any future runtime.

Multiple runtimes should be capable of executing the same Skill.

---

## Reusable

Skills should be reusable across domains whenever possible.

Example

Research

can be used by

- software engineering
- business
- academia
- personal productivity
- market analysis

---

## Observable

Execution of a Skill should expose measurable progress.

---

## Composable

Multiple Skills may work together to complete a Work Package.

---

# Examples

Examples of Skills include

- Research
- Root Cause Analysis
- Bug Resolution
- Architecture Review
- Documentation
- Planning
- Code Review
- Refactoring
- Summarization
- Release Preparation
- Risk Assessment
- Dependency Analysis
- Testing
- Validation
- Monitoring

Skills describe operational capability.

---

# Skill Structure

Every Skill contains

## Identity

- identifier
- name
- version

---

## Purpose

Defines

What capability does this Skill provide?

---

## Inputs

Required information.

Examples

Repository

Research Question

Document

Calendar

Workspace

Context Package

---

## Outputs

Expected deliverables.

Examples

Report

Implementation

Summary

Presentation

Documentation

Review

---

## Required Context

Defines what Context Engineering must provide before execution.

Examples

Repository

Architecture

Historical Decisions

Research Sources

Calendar

Existing Tasks

---

## Constraints

Defines operational boundaries.

Examples

Approval Required

Budget

Security

Workspace Restrictions

Deadlines

Quality Requirements

---

## Procedure

Defines the operational methodology.

The procedure should describe

- phases
- checkpoints
- expected transitions

without binding to a runtime.

---

## Validation Strategy

Defines how completion should be verified.

Examples

Tests

Review

Evidence

Generated Artifacts

Independent Verification

---

## Recovery Strategy

Defines expected behavior when execution fails.

Examples

Retry

Escalate

Request Context

Pause

Human Review

---

# Skill Lifecycle

```
Registered

↓

Selected

↓

Prepared

↓

Executing

↓

Validated

↓

Completed
```

Failure states

```
Blocked

Failed

Cancelled

Expired
```

---

# Skill Categories

Skills may belong to categories.

Examples

## Analysis

Research

Root Cause Analysis

Architecture Review

Risk Assessment

---

## Development

Implementation

Refactoring

Testing

Code Review

---

## Documentation

Writing

Summarization

Knowledge Capture

Review

---

## Operations

Planning

Monitoring

Release

Migration

Validation

---

## Personal

Task Planning

Calendar Organization

TODO Management

Goal Tracking

---

# Skill Selection

Planning determines

what capabilities are required.

Skill Selection determines

which Skills satisfy those capabilities.

Selection should consider

- capability
- context
- constraints
- evidence requirements

Skill Selection never considers runtimes.

---

# Skill Composition

Complex work may require multiple Skills.

Example

```
Resolve Production Bug

↓

Root Cause Analysis

↓

Repository Analysis

↓

Implementation

↓

Testing

↓

Documentation

↓

Validation
```

Each Skill contributes one capability.

---

# Skill Registry

Skills should be discoverable through a registry.

The registry maintains

- available Skills
- versions
- metadata
- categories
- compatibility
- required context

The registry does not perform execution.

---

# Relationship with Runtimes

Skills define

what should happen.

Runtimes determine

who performs the work.

Example

```
Skill

↓

Execution Strategy

↓

Runtime
```

The same Skill may execute on

Claude Code

Gemini

Nexus Agent

Human Operator

Future runtimes

without modification.

---

# Architectural Boundaries

Skills

✓ define operational capability

✓ define required context

✓ define expected outputs

✓ define validation

✓ define recovery guidance

Skills never

✗ execute work

✗ choose runtimes

✗ perform orchestration

✗ build context

Those responsibilities belong to other capability layers.

---

# Future Evolution

Future versions may support

- parameterized Skills

- hierarchical Skills

- organization-specific Skills

- learned Skills

- versioned operational procedures

- marketplace Skills

These enhancements should preserve the architectural principles defined here.

---

# North Star

Skills are reusable operational capabilities.

They describe how work should be accomplished without depending on any execution technology.

Capabilities remain stable.

Execution technologies evolve.