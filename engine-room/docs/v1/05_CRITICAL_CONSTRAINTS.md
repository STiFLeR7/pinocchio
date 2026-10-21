# 05_CRITICAL_CONSTRAINTS.md

# Nexus Critical Constraints

Version: 0.1

Status: Mandatory

Project: Nexus

Priority: Highest

---

# Purpose

This document defines the non-negotiable constraints that govern Nexus.

These constraints exist to prevent:

* Architectural drift
* Accidental complexity
* Unsafe execution
* State corruption
* Agent overreach
* Governance failures

If any implementation conflicts with this document:

This document wins.

Always.

---

# Golden Rule

Nexus is an orchestration system.

Not an AI assistant.

Not a chatbot.

Not an autonomous agent framework.

Every implementation decision must reinforce:

Orchestration

Governance

Persistence

Auditability

Recoverability

If a feature moves Nexus away from those goals, it should not be implemented.

---

# Constraint 1

Human Governance Is Mandatory

Nexus must never become the final decision maker.

Allowed:

Recommendations

Plans

Research

Summaries

Drafts

Forbidden:

Approvals

Governance Decisions

Repository Mutation Without Approval

External Actions Without Approval

Deployment Decisions

Production Changes Without Approval

Humans remain the final authority.

Always.

---

# Constraint 2

Memory Is Mandatory

Nexus must never operate as a stateless system.

Every important event must persist.

Required Persistence:

Tasks

Approvals

Executions

Research

Notifications

Reports

Audit Events

Preferences

Workflow State

State loss is considered a critical failure.

---

# Constraint 3

Discord Is An Interface

Discord is not the source of truth.

Never store business state in Discord.

Never rely on Discord messages as system memory.

Discord exists only as a communication layer.

All state belongs to Nexus Memory.

---

# Constraint 4

Email Is An Interface

Email is not the source of truth.

Email messages may be lost.

Email messages may be delayed.

System state must never depend on email delivery.

Email is a delivery mechanism only.

---

# Constraint 5

LLMs Are Reasoning Engines

LLMs are infrastructure.

Not authorities.

Allowed:

Research

Summarization

Planning

Classification

Drafting

Explanation

Forbidden:

Approvals

Execution Authorization

Workflow Ownership

Memory Ownership

Governance Ownership

Nexus owns those responsibilities.

---

# Constraint 6

Execution Must Be Controlled

Execution is the highest-risk subsystem.

No direct execution is allowed.

Every execution requires:

Task

Approval

Audit Trail

Repository Validation

Execution Record

Result Record

Execution without traceability is prohibited.

---

# Constraint 7

No Arbitrary Repository Access

Nexus may only operate on approved repositories.

Required:

Repository Registry

Example:

repositories:

nexus:
path: D:/projects/nexus

memex:
path: D:/projects/memex

fosterx:
path: D:/projects/fosterx

Any repository not registered is inaccessible.

---

# Constraint 8

No Arbitrary Command Execution

Nexus must never become a shell proxy.

Forbidden:

rm -rf

Arbitrary PowerShell

Arbitrary Bash

User-supplied shell commands

Allowed:

Structured execution requests

Examples:

Run Gemini CLI

Run Claude Code

Generate Report

Analyze Repository

Execution must be constrained.

---

# Constraint 9

Deterministic Routing

Agent routing must not depend on an LLM.

Routing should be rule-based.

Example:

Research Request
→ Research Agent

Approval Request
→ Approval Engine

Execution Request
→ Execution Agent

Routing must remain predictable.

---

# Constraint 10

Every Workflow Must Be Recoverable

System restart must not destroy workflows.

Required:

Checkpointing

Workflow Persistence

State Recovery

Restart Safety

After restart:

Nexus must know:

* What was running
* What completed
* What failed
* What requires retry

---

# Constraint 11

Every Action Must Be Auditable

Nexus must produce a complete audit trail.

Examples:

Task Created

Task Updated

Approval Granted

Approval Rejected

Execution Started

Execution Completed

Execution Failed

Research Generated

Summary Generated

Auditability is mandatory.

---

# Constraint 12

Integrations Must Be Replaceable

Discord may change.

Email providers may change.

Models may change.

Gemini may change.

Claude may change.

Business logic must not depend on vendor-specific implementations.

Use abstraction layers.

Always.

---

# Constraint 13

Models Must Be Replaceable

Never tightly couple logic to:

Nemotron

OwlAlpha

DeepSeek

Qwen

Future models

Required:

Provider Interface

Model Interface

Router Interface

Models are plugins.

Not architecture.

---

# Constraint 14

OpenRouter Is A Gateway

OpenRouter is infrastructure.

Not business logic.

If OpenRouter disappears tomorrow:

Only the adapter should change.

The architecture should survive.

---

# Constraint 15

Failure Is Normal

Nexus must assume failure.

Expected Failures:

Network Failure

Discord Failure

Email Failure

Provider Failure

Model Failure

Process Failure

Restart

Database Lock

Every subsystem requires recovery paths.

---

# Constraint 16

Retry Everything Important

Critical operations require retries.

Examples:

Email Delivery

Discord Messages

OpenRouter Requests

Research Jobs

Execution Reporting

Retries must be bounded.

Infinite retry loops are forbidden.

---

# Constraint 17

Logging Is Not Optional

Every subsystem must emit structured logs.

Required Fields:

Timestamp

Component

Event Type

Status

Correlation ID

Task ID

Logs are part of the product.

Not a debugging afterthought.

---

# Constraint 18

Architecture Before Code

Implementation must never begin with coding.

Required Sequence:

Understand

Model

Visualize

Design

Review

Implement

Architecture-first development is mandatory.

---

# Constraint 19

Visual Explanations Are Mandatory

When architecture changes:

Always generate:

Component Diagram

Data Flow Diagram

Sequence Diagram

Failure Flow Diagram

Required Skills:

brainstorming:superpowers

visual-companion

Architecture should be visible.

Not hidden in code.

---

# Constraint 20

No Hidden State

State must be explicit.

Forbidden:

Global Variables

Silent Caches

Undocumented Files

Implicit Runtime State

All important state belongs in the Memory Layer.

---

# Constraint 21

Single Source Of Truth

The source of truth is Nexus Memory.

Not:

Discord

Email

Gemini

Claude

OpenRouter

Logs

Everything important must eventually resolve to Nexus Memory.

---

# Constraint 22

Agent Independence

Agents should be replaceable.

Research Agent should not depend on:

Execution Agent

Execution Agent should not depend on:

Communication Agent

Loose coupling is required.

---

# Constraint 23

Testability Is Mandatory

Every major component must be testable in isolation.

Required:

Unit Tests

Integration Tests

End-to-End Tests

A component that cannot be tested independently is incorrectly designed.

---

# Constraint 24

Security Through Constraints

Nexus should minimize risk by limiting capability.

Prefer:

Allow Lists

Explicit Registries

Controlled Execution

Structured Inputs

Avoid:

Unlimited Access

Dynamic Execution

Unrestricted Commands

Security should emerge from architecture.

---

# Constraint 25

Pi Must Be Evaluated First

Before implementing orchestration primitives:

Evaluate:

https://github.com/earendil-works/pi

Questions:

Can Pi provide:

* Workflow orchestration?
* Agent lifecycle management?
* Runtime coordination?
* State management?

Do not rebuild capabilities without evaluation.

Document conclusions.

---

# Constraint 26

Production Quality Is Required

MVP does not mean prototype.

MVP means:

Minimal Scope

Production Standards

Required:

Typing

Testing

Documentation

Logging

Recovery

Observability

Maintainability

Production quality is mandatory.

---

# Constraint 27

No Silent Automation

Every autonomous action must be explainable.

For any action Nexus performs:

It must be possible to answer:

Why did this happen?

Who triggered it?

What state changed?

What was executed?

What was the result?

If the answer is unavailable:

The design is wrong.

---

# Final Principle

Nexus is a governed orchestration platform.

Memory owns truth.

Humans own authority.

Agents provide capability.

Execution is controlled.

Everything is auditable.

Nothing important is implicit.
