# 01_ARCHITECTURE.md

# Nexus Architecture

Version: 0.1

Status: Source of Truth

Project: Nexus

---

# Overview

Nexus is an AI Orchestration Control Plane.

It is not a chatbot.

It is not a single-agent framework.

It is not a wrapper around LLM APIs.

Nexus exists to coordinate:

* Humans
* Tasks
* Approvals
* Communication Channels
* AI Agents
* Execution Systems
* Memory
* Schedulers

through a deterministic, auditable, and recoverable orchestration layer.

The architecture prioritizes:

1. Deterministic execution
2. Persistent state
3. Human governance
4. Fault tolerance
5. Observability
6. Testability

---

# High-Level Architecture

```
                             ┌──────────────────────┐
                             │        USER          │
                             │ Director / Operator  │
                             └──────────┬───────────┘
                                        │
                                        │
                                        ▼
```

┌────────────────────────────────────────────────────────────────────────────┐
│                        COMMUNICATION LAYER                                 │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│   Discord Bot      WhatsApp Gateway      Email Gateway      Future APIs    │
│                                                                            │
└──────────────┬─────────────────┬─────────────────┬─────────────────────────┘
│                 │                 │
└─────────────────┴─────────────────┘
│
▼

┌────────────────────────────────────────────────────────────────────────────┐
│                           EVENT GATEWAY                                    │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│ - Message Normalization                                                    │
│ - Event Validation                                                         │
│ - Authentication                                                           │
│ - Channel Routing                                                          │
│ - Intent Extraction                                                        │
│                                                                            │
└───────────────────────────────┬────────────────────────────────────────────┘
│
▼

┌────────────────────────────────────────────────────────────────────────────┐
│                           NEXUS CORE                                       │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  ┌────────────┐   ┌────────────┐   ┌────────────┐   ┌────────────┐         │
│  │ Task Engine│   │Approval Eng│   │Agent Router│   │Rule Engine │         │
│  └─────┬──────┘   └─────┬──────┘   └─────┬──────┘   └─────┬──────┘         │
│        │                │                │                │                │
│        └────────────────┼────────────────┼────────────────┘                │
│                         │                │                                 │
│                         ▼                ▼                                 │
│                                                                            │
│                 Workflow Orchestrator                                      │
│                                                                            │
└───────────────────────────────┬────────────────────────────────────────────┘
│
│
┌───────────────────────┼──────────────────────────┐
│                       │                          │
▼                       ▼                          ▼

┌──────────────────┐ ┌──────────────────┐ ┌────────────────────┐
│ Scheduling Layer │ │ Memory Layer     │ │ Intelligence Layer │
└─────────┬────────┘ └────────┬─────────┘ └──────────┬─────────┘
│                   │                      │
│                   │                      │
▼                   ▼                      ▼

APScheduler          State Store           OpenRouter Router
Cron Jobs            SQLite/Postgres       Fallback Engine

```
                                              │
                                              ▼

                               ┌────────────────────────┐
                               │    Model Providers     │
                               ├────────────────────────┤
                               │ Nemotron              │
                               │ OwlAlpha              │
                               │ DeepSeek              │
                               │ Future Models         │
                               └──────────┬────────────┘
                                          │
                                          ▼
```

┌────────────────────────────────────────────────────────────────────────────┐
│                         EXECUTION LAYER                                    │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│   Gemini CLI Runner                                                        │
│   Claude Code Runner                                                       │
│   Research Jobs                                                            │
│   Repository Operations                                                    │
│                                                                            │
└───────────────────────────────┬────────────────────────────────────────────┘
│
▼

┌────────────────────────────────────────────────────────────────────────────┐
│                           REPOSITORY LAYER                                │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│   Allowlisted Repositories Only                                            │
│                                                                            │
│   - Nexus                                                                   │
│   - Memex                                                                    │
│   - FosterX                                                                  │
│   - Future Repositories                                                      │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘

---

# Architectural Layers

Nexus is organized into six major layers.

Communication Layer

↓

Event Gateway

↓

Nexus Core

↓

Memory + Scheduling + Intelligence

↓

Execution Layer

↓

Repository Layer

Each layer has a single responsibility.

No layer should bypass another layer.

---

# Layer 1: Communication Layer

Purpose:

External interfaces into Nexus.

Responsibilities:

* Receive user requests
* Send notifications
* Deliver reports
* Deliver approval requests

Supported Interfaces:

Discord

Primary interface.

WhatsApp

Mobile communication interface.

Email

Formal communication interface.

Future:

* Slack
* Teams
* Web UI
* API

Rules:

Communication adapters must never contain business logic.

Adapters only translate messages into Nexus events.

---

# Layer 2: Event Gateway

Purpose:

Convert external events into internal events.

Responsibilities:

* Validation
* Authentication
* Routing
* Event normalization

Example:

Discord Message

↓

Discord Event

↓

Normalized Nexus Event

↓

Task Request

This layer prevents communication channels from leaking implementation details.

---

# Layer 3: Nexus Core

Purpose:

Brain of the system.

Contains orchestration logic.

Components:

Task Engine

Responsible for:

* Task creation
* Task lifecycle
* Task prioritization

Approval Engine

Responsible for:

* Approval requests
* Approval tracking
* Approval auditing

Agent Router

Responsible for:

* Selecting execution agent
* Routing requests

Rule Engine

Responsible for:

* Governance
* Workflow policies
* Safety controls

Workflow Orchestrator

Responsible for:

* End-to-end workflow execution

This is the most important component.

All workflows pass through the orchestrator.

---

# Layer 4: Memory Layer

Purpose:

Persistent state.

Nexus must survive restarts.

Memory stores:

* Tasks
* Approvals
* Executions
* Research
* Summaries
* User preferences

Properties:

Persistent

Recoverable

Auditable

Queryable

Future:

Postgres

Vector memory

Knowledge graph

---

# Layer 5: Scheduling Layer

Purpose:

Time-based orchestration.

Examples:

Daily Summary

Research Jobs

Reminders

Approval Escalations

Task Follow-ups

Implementation:

APScheduler

Future:

Distributed scheduler

---

# Layer 6: Intelligence Layer

Purpose:

Reasoning only.

Never orchestration.

Responsibilities:

* Research
* Summarization
* Planning
* Draft generation

Never:

* Direct execution
* Direct approvals
* State mutation

Architecture:

Nexus Core

↓

Model Router

↓

Provider Abstraction

↓

OpenRouter

↓

Model

This ensures models remain replaceable infrastructure.

---

# Model Routing Flow

```
                Request
                    │
                    ▼

          OpenRouter Router
                    │
                    ▼

             Primary Model
               Nemotron
                    │
         ┌──────────┴──────────┐
         │                     │
         ▼                     ▼

      Success              Failure
                               │
                               ▼

                         OwlAlpha
                               │
                 ┌─────────────┴─────────────┐
                 │                           │
                 ▼                           ▼

              Success                   Failure
                                               │
                                               ▼

                                           DeepSeek
                                               │
                                               ▼

                                           Result
```

Circuit breakers must exist for:

* Rate limits
* Timeouts
* Provider failures

---

# Execution Architecture

Execution is isolated.

Nexus Core never executes directly.

Flow:

Task

↓

Approval

↓

Execution Request

↓

Execution Layer

↓

Agent Runner

↓

Repository

↓

Result

↓

Audit Event

Supported Runners:

Gemini CLI Runner

Claude Code Runner

Future:

* Codex
* OpenHands
* Aider

---

# Approval Workflow

```
              Task Created
                     │
                     ▼

            Approval Required
                     │
                     ▼

          Discord Approval Card
                     │
        ┌────────────┴────────────┐
        │                         │
        ▼                         ▼

     Approved                 Rejected
        │                         │
        ▼                         ▼

  Execution Queue            Closed
```

All approvals must be persisted.

All approval actions must be audited.

---

# State Flow

Message

↓

Event

↓

Task

↓

Approval

↓

Execution

↓

Result

↓

Summary

↓

Memory

Nothing should disappear.

Everything important must be stored.

---

# Failure Recovery

Nexus assumes failures are normal.

Required recovery:

Model Failure

↓

Fallback Model

Execution Failure

↓

Retry Policy

Discord Failure

↓

Retry Queue

Restart

↓

State Recovery

Database Failure

↓

Backup Recovery

All workflows must be resumable.

---

# Observability Architecture

Every action emits events.

Task Created

Task Updated

Approval Requested

Approval Granted

Execution Started

Execution Completed

Execution Failed

Research Started

Research Completed

These events feed:

* Logs
* Audits
* Summaries
* Monitoring

---

# Future Architecture Evolution

v0.1

Monolith

SQLite

Single Runtime

Single Worker

v0.5

Modular Services

Postgres

Redis

Distributed Scheduler

v1.0

Multi-Agent Runtime

Advanced Memory

Knowledge Graph

Multi-User Governance

Horizontal Scaling

---

# Architectural Principle

Nexus is a deterministic orchestration system that uses AI for reasoning.

AI assists the system.

AI does not control the system.
