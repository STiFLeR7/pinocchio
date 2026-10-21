# 07_REFERENCES.md

# Nexus References

Version: 0.1

Status: Required Reading

Project: Nexus

---

# Purpose

This document contains external references that may influence Nexus architecture, implementation, workflows, and operational design.

References are provided to:

* Accelerate development
* Avoid reinventing proven solutions
* Learn from existing systems
* Evaluate reusable patterns

References are not architecture.

References are not requirements.

References are not source of truth.

The source of truth remains:

* 00_BRIEF.md
* 01_ARCHITECTURE.md
* 02_TECH_STACK.md
* 03_AGENT_DESIGN.md
* 04_CRITICAL_CONSTRAINTS.md
* 05_INTEGRATION_SPECS.md
* 06_DEVELOPMENT_PHASES.md
* RULES.md

---

# Reference Evaluation Policy

For every reference:

Required:

1. Analyze
2. Extract useful patterns
3. Compare against Nexus architecture
4. Document findings
5. Decide whether to adopt

Forbidden:

Blind copying

Blind dependency adoption

Architecture replacement

Framework worship

Every external system must justify its inclusion.

---

# Reference 1

Pi

Repository:

https://github.com/earendil-works/pi

Category:

Orchestration Framework

Priority:

Critical

Status:

Mandatory Evaluation

---

## Why It Matters

Pi may provide:

* Workflow orchestration
* Runtime coordination
* Agent lifecycle management
* State handling
* Task execution patterns

Potential Benefits:

Reduced implementation effort.

Potential Risks:

Architectural mismatch.

---

## Required Evaluation Questions

Can Pi provide:

Workflow execution?

State management?

Agent orchestration?

Task coordination?

Scheduling primitives?

Failure recovery?

Persistence?

Observability?

---

## Decision Outcomes

Option A

Adopt Pi

Option B

Partial Integration

Option C

Reject

Decision must be documented.

---

# Reference 2

Nexus Agent

Repository:

https://github.com/nousresearch/hermes-agent

Category:

Agent Runtime

Priority:

Critical

Status:

Mandatory Evaluation

---

## Environment Note

Nexus Agent is already installed locally.

Available from terminal:

PowerShell:

nexus

Command Prompt:

nexus

This means Nexus can be treated as an available runtime rather than a future dependency.

---

## Why It Matters

Nexus Agent provides an existing agent execution environment.

Potential capabilities:

* Agent execution
* Tool calling
* Task execution
* Workflow automation
* Runtime management

Rather than building everything from scratch, Nexus should evaluate whether Nexus can act as a worker runtime.

---

## Evaluation Goals

Determine:

Can Nexus act as:

Research Agent?

Planning Agent?

Execution Agent?

Task Worker?

Background Worker?

Autonomous Runtime?

Tool Executor?

---

## Architectural Position

Possible Future Architecture

```
                     Nexus
                       │
                       ▼

              Execution Layer
                       │

    ┌──────────────────┼──────────────────┐

    ▼                  ▼                  ▼
```

Gemini CLI         Claude Code       Nexus Agent

```
                       │

                       ▼

                   Results
```

In this model:

Nexus remains orchestrator.

Nexus remains runtime.

Governance remains inside Nexus.

---

## Critical Constraint

Nexus must never become the source of truth.

Nexus must never own:

Approvals

Memory

Governance

Task Authority

Execution Authorization

Those responsibilities remain inside Nexus.

---

## Required Investigation

Document:

Installation method

CLI interface

Execution model

Configuration model

State model

Memory model

Tool calling capabilities

Logging capabilities

Extensibility

Failure recovery

Runtime characteristics

---

## Decision Outcomes

Option A

Primary Runtime

Option B

Secondary Runtime

Option C

Specialized Runtime

Option D

Rejected

Decision must be documented.

---

# Reference 3

Gemini CLI

Category:

Execution Runtime

Status:

Approved

Priority:

Critical

---

## Purpose

Primary implementation runtime.

Responsibilities:

Code generation

Architecture generation

Documentation

Refactoring

Repository operations

Workflow execution

---

## Evaluation Focus

Strengths

Weaknesses

Execution reliability

Context management

Automation capabilities

Integration patterns

---

# Reference 4

Claude Code

Category:

Execution Runtime

Status:

Approved

Priority:

Critical

---

## Purpose

Deep engineering execution runtime.

Responsibilities:

Large-scale refactoring

Architecture analysis

Complex implementation

Code review

Repository understanding

---

## Evaluation Focus

Long-context performance

Code quality

Architectural reasoning

Automation workflows

Execution safety

---

# Reference 5

OpenRouter

Website:

https://openrouter.ai

Category:

Model Gateway

Status:

Approved

Priority:

Critical

---

## Purpose

Unified model access layer.

Benefits:

Single integration point.

Model abstraction.

Fallback management.

Cost control.

---

## Required Evaluation Areas

Provider reliability

Rate limits

Model availability

Failure modes

Fallback behavior

Usage tracking

---

# Reference 6

Discord

Category:

Primary User Interface

Status:

Approved

Priority:

Critical

---

## Purpose

Human governance interface.

Examples:

Task management

Approvals

Notifications

Operational visibility

Daily reports

---

## Evaluation Focus

Workflow design

Approval UX

Embed design

Interaction design

Operational ergonomics

---

# Reference 7

Email Systems

Category:

Communication Layer

Status:

Approved

Priority:

High

---

## Purpose

Formal communication channel.

Examples:

Reports

Approvals

Notifications

Digests

Reminders

---

## Evaluation Focus

Template design

Delivery reliability

Formatting

Auditability

Retry handling

---

# Reference 8

Agentic System Patterns

Category:

Architectural Reference

Status:

Ongoing

Priority:

Medium

---

## Purpose

Study existing orchestration systems.

Focus:

Control planes

Workflow engines

Task schedulers

State machines

Distributed orchestration

Agent runtimes

---

## Rule

Borrow ideas.

Do not borrow complexity.

Nexus should remain simple.

---

# Reference Documentation Requirement

Every evaluated reference must generate:

Reference Report

Containing:

Summary

Strengths

Weaknesses

Architectural Fit

Adoption Recommendation

Decision

No reference should be adopted without evaluation.

---

# Architectural Reminder

Nexus is not attempting to compete with:

Gemini CLI

Claude Code

Nexus Agent

Pi

OpenRouter

Those systems are capabilities.

Nexus is the orchestrator that coordinates them.

---

# Final Principle

References provide options.

Architecture provides direction.

Nexus should learn from existing systems while remaining opinionated, deterministic, governed, and memory-driven.

External tools are replaceable.

Nexus remains authoritative.
