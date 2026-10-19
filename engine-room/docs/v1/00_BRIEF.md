# 00_BRIEF.md

# Nexus

Version: 0.1

Status: Foundational Brief

Owner: Hill Patel

---

# Executive Summary

Nexus is an AI Orchestration Control Plane designed to function as a persistent digital operations manager.

Unlike traditional AI assistants that focus on conversation, Nexus focuses on orchestration.

Its primary responsibility is coordinating:

* Tasks
* Approvals
* Research
* Communication
* Scheduling
* Execution
* Memory
* Agent Runtimes

through a deterministic, auditable, and recoverable workflow engine.

Nexus acts as the operational layer between humans and AI execution systems.

It enables a human operator to delegate work, review approvals, trigger actions, receive intelligence updates, and manage long-running workflows through familiar communication channels such as Discord, Email, and WhatsApp.

---

# Why Nexus Exists

Modern AI systems are powerful at reasoning but weak at operations.

They can generate plans.

They can summarize information.

They can write code.

However they struggle with:

* Long-term state
* Task tracking
* Workflow governance
* Approval processes
* Operational continuity
* Reliable execution

Nexus exists to bridge that gap.

The goal is not to create a smarter model.

The goal is to create a more reliable system.

---

# Problem Statement

Today, AI tools are fragmented.

A user may:

* Chat with an LLM
* Store notes elsewhere
* Manage tasks separately
* Track approvals manually
* Run agents from terminals
* Monitor outputs through multiple tools

This creates operational overhead.

Information becomes fragmented.

Context becomes lost.

Tasks become forgotten.

Approvals become inconsistent.

Execution becomes difficult to audit.

Nexus centralizes these responsibilities into a single orchestration layer.

---

# Vision

The long-term vision is to create a system that behaves like a trusted Chief of Staff.

The system should:

* Remember context
* Track commitments
* Manage execution
* Coordinate AI agents
* Request approvals
* Deliver summaries
* Surface important information

while remaining under human governance.

Nexus should become the operational interface through which work is coordinated.

---

# Core Philosophy

Nexus follows one principle:

AI should assist execution.

AI should not control execution.

Human governance remains the final authority.

All execution paths must remain observable, auditable, and interruptible.

---

# What Nexus Is

Nexus is:

* An orchestration platform
* A workflow engine
* A task coordinator
* A memory-driven system
* An approval framework
* A communication hub
* An execution router
* A scheduling platform
* A research assistant

Nexus is designed around persistent state and deterministic workflows.

---

# What Nexus Is Not

Nexus is not:

* A chatbot
* A Discord bot project
* A wrapper around OpenRouter
* A replacement for software engineering judgment
* A fully autonomous AGI
* An uncontrolled agent framework
* A prompt collection

Conversation is a feature.

Orchestration is the product.

---

# Initial Target User

Primary User:

Hill Patel

AI Engineer

Technical operator

Builder

Researcher

The initial version should optimize for a single power user.

Multi-user support is a future concern.

---

# Primary Use Cases

## Task Management

Examples:

* Follow up on research
* Track project work
* Monitor deliverables
* Schedule reminders

---

## Approval Workflows

Examples:

* Share document with client
* Run repository changes
* Execute agent tasks
* Trigger deployments

Approval requests should route through Discord.

---

## AI Agent Execution

Examples:

* Launch Gemini CLI
* Launch Claude Code
* Run research jobs
* Generate reports

All execution must be auditable.

---

## Research Operations

Examples:

* AI news monitoring
* Paper monitoring
* Competitor monitoring
* Technology tracking

Research should run unattended when scheduled.

---

## Daily Intelligence Reports

Examples:

* AI news digest
* Research digest
* Open tasks
* Pending approvals
* Execution summaries

Delivered through Discord and Email.

---

# Communication Channels

Nexus should support multiple communication interfaces.

Primary:

Discord

Secondary:

Email

Future:

WhatsApp

Slack

Teams

Web Dashboard

Communication channels are interfaces.

They are not sources of truth.

---

# Source of Truth

The source of truth is Nexus State.

Not Discord.

Not Email.

Not WhatsApp.

Not OpenRouter.

Not Gemini CLI.

All important information must persist in Nexus memory.

---

# Memory Philosophy

Memory is mandatory.

Nexus should never operate as a stateless system.

The system must persist:

* Tasks
* Approvals
* Executions
* Research
* Summaries
* User preferences
* Workflow history

The system must survive restarts without losing context.

---

# Agent Philosophy

LLMs are tools.

Not decision makers.

Nexus owns orchestration.

Models provide reasoning.

Models do not:

* Approve actions
* Mutate critical state
* Execute commands directly

The orchestration layer remains deterministic.

---

# Pi Evaluation Requirement

Before implementing orchestration primitives, evaluate:

https://github.com/earendil-works/pi

Determine whether Pi can provide:

* Workflow execution
* Agent coordination
* Runtime orchestration
* State management

Reuse proven infrastructure where beneficial.

Avoid rebuilding capabilities that already exist.

Document findings.

---

# Visual-First Architecture Requirement

Every architecture discussion must include diagrams.

Mandatory skill usage:

* brainstorming:superpowers
* visual-companion

Required outputs:

* Component diagrams
* Workflow diagrams
* Sequence diagrams
* Failure flow diagrams

Architecture must be explainable visually.

---

# MVP Scope

The MVP focuses on proving orchestration.

Required capabilities:

Task Creation

Task Persistence

Approval Workflows

Discord Integration

Email Integration

Scheduling

OpenRouter Integration

Model Fallback

Gemini CLI Execution

Claude Code Execution

Daily Summaries

Research Jobs

Persistent State

Audit Logging

Test Coverage

The MVP should remain intentionally narrow.

---

# Out of Scope

The following are intentionally deferred:

Multi-user tenancy

Knowledge graph memory

Vector search

RAG systems

Multi-agent swarms

Complex planning systems

Autonomous deployments

Advanced dashboards

Mobile applications

Voice interfaces

These can be added later.

They are not MVP requirements.

---

# Success Criteria

The MVP is successful if:

A task can be created.

The task is persisted.

The task requests approval.

Approval is granted through Discord.

Execution launches Gemini CLI or Claude Code.

Results are recorded.

The workflow survives restart.

A daily summary is generated.

All actions are auditable.

The system can run unattended.

---

# Failure Criteria

The MVP fails if:

State is lost after restart.

Approvals can be bypassed.

Execution is not auditable.

Workflows become model-dependent.

Discord becomes the source of truth.

The system behaves as a chatbot rather than an orchestrator.

The architecture becomes difficult to test.

The architecture becomes difficult to recover.

---

# North Star

Nexus should eventually become a trusted operational control plane that continuously manages tasks, context, approvals, research, and execution while remaining transparent, recoverable, and governed by human intent.

Every implementation decision should move the system toward that goal.
