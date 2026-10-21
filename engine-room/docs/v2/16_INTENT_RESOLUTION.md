# Intent Resolution

Status: Target Architecture

---

# Purpose

Intent Resolution is responsible for transforming raw operator requests into normalized operational goals.

It is the first operational capability of Nexus.

Before Context Engineering, Planning, or Execution can begin, Nexus must understand what the operator actually intends.

Intent Resolution removes ambiguity, identifies missing information, determines scope, and constructs a well-defined Goal for the rest of the platform.

---

# Why Intent Resolution Exists

Operators communicate naturally.

Operational systems require precision.

These are fundamentally different.

Example

```
Fix the issue.
```

Questions immediately arise.

- Which issue?
- Which repository?
- Production or development?
- Bug or enhancement?
- High priority or low priority?
- What does "fixed" mean?

Intent Resolution bridges natural human communication and deterministic operational execution.

---

# Architectural Position

Intent Resolution is the entry point of Nexus.

```
Operator

↓

Intent Resolution

↓

Goal

↓

Context Engineering

↓

Planning
```

Every operational request must pass through Intent Resolution.

---

# Design Principles

## Human First

Operators should express goals naturally.

The platform should adapt to humans.

Humans should not adapt to the platform.

---

## Goal Oriented

Intent Resolution produces Goals.

It never produces execution plans.

---

## Clarification Before Assumption

When ambiguity exists,

the platform should prefer clarification over assumptions.

Assumptions should only occur when explicitly permitted by operational policy.

---

## Domain Agnostic

Intent Resolution should operate consistently across every operational domain.

Examples

- Software Engineering
- Research
- Writing
- Documentation
- Business Operations
- Personal Productivity
- Infrastructure
- Planning
- Analysis

Only the domain changes.

The process remains consistent.

---

## Explainable

Every interpreted Goal should explain

- what was understood
- what assumptions were made
- what information was missing
- why clarification was requested

---

# Responsibilities

Intent Resolution is responsible for

- understanding operator requests
- identifying ambiguity
- determining operational scope
- identifying missing information
- constructing Goals
- identifying operational domain
- identifying urgency
- estimating confidence

Intent Resolution never

- builds context
- creates plans
- performs execution
- selects runtimes

---

# Operational Lifecycle

```
Operator Request

↓

Intent Detection

↓

Ambiguity Analysis

↓

Scope Resolution

↓

Constraint Discovery

↓

Goal Normalization

↓

Goal
```

---

# Inputs

Intent Resolution accepts

- natural language
- structured requests
- conversations
- voice transcripts
- future interaction modalities

Input format should not affect operational behavior.

---

# Outputs

Intent Resolution produces

- Goal
- Goal Metadata
- Confidence
- Missing Information
- Clarification Requests
- Domain Classification
- Priority Estimate

These outputs become inputs for Context Engineering.

---

# Intent Analysis

Intent Resolution attempts to determine

## Objective

What outcome is desired?

---

## Domain

Which operational domain is involved?

Examples

Software

Research

Writing

Planning

Operations

Personal

Business

---

## Scope

What work is included?

What work is excluded?

---

## Constraints

Known constraints.

Examples

Time

Budget

Governance

Deadlines

Resources

---

## Priority

Operational urgency.

Examples

Critical

High

Medium

Low

Background

---

# Ambiguity Detection

Intent Resolution should actively detect ambiguity.

Examples

Missing workspace

Missing repository

Multiple possible goals

Conflicting instructions

Undefined deliverables

Incomplete constraints

Missing approvals

Ambiguity should never silently propagate through the platform.

---

# Clarification

When ambiguity exceeds acceptable confidence,

Intent Resolution should generate clarification requests.

Example

Operator

```
Fix the issue.
```

Clarification

```
Which repository?

Which issue?

Expected outcome?

Priority?
```

Clarification is preferred over incorrect execution.

---

# Goal Normalization

Different operator requests may produce the same Goal.

Examples

```
Fix this bug.

Resolve production issue.

Repair authentication failure.
```

↓

```
Goal

Resolve Authentication Failure
```

Goal normalization creates consistency across the platform.

---

# Confidence

Intent Resolution should estimate confidence.

Possible levels

High

Medium

Low

Unknown

Low confidence may require clarification before Context Engineering begins.

---

# Relationship with Context Engineering

Intent Resolution determines

what the Goal is.

Context Engineering determines

what information is required.

Responsibilities remain independent.

---

# Relationship with Planning

Planning assumes the Goal has already been normalized.

Planning should never reinterpret operator intent.

---

# Relationship with Governance

Governance may restrict certain goals.

Intent Resolution does not enforce governance.

It only identifies intent.

---

# Architectural Boundaries

Intent Resolution

✓ understands requests

✓ resolves ambiguity

✓ creates Goals

✓ estimates confidence

✓ requests clarification

Intent Resolution never

✗ performs execution

✗ builds context

✗ creates plans

✗ performs validation

---

# Future Evolution

Future versions may introduce

- conversational clarification

- intent history

- organizational intent patterns

- predictive goal completion

- personalized intent interpretation

These capabilities should preserve deterministic Goal construction.

---

# North Star

Intent Resolution transforms natural human communication into deterministic operational goals.

It is the bridge between how humans express work and how Nexus understands work.

Every operational capability depends on the quality of the Goal produced here.

Nexus should never execute what it does not first understand.