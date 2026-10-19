# 03_AGENT_DESIGN.md

# Nexus Agent Design

Version: 0.1

Status: Source of Truth

Project: Nexus

---

# Purpose

This document defines how intelligence, agents, orchestration, memory, and execution interact within Nexus.

The goal is to establish a clear separation between:

* Orchestration
* Reasoning
* Execution
* Memory

These concerns must never become tightly coupled.

---

# Core Principle

Nexus is not an agent.

Nexus is an orchestration system.

Agents are resources managed by Nexus.

This distinction is critical.

Wrong Model:

User
↓
Agent
↓
Everything

Correct Model:

User
↓
Nexus
↓
Agent
↓
Result

Nexus remains in control at all times.

---

# Design Philosophy

Most AI systems place the LLM at the center.

Nexus places orchestration at the center.

Architecture:

```
             Nexus
                │
┌───────────────┼───────────────┐
│               │               │
▼               ▼               ▼
```

Memory        Governance      Execution

```
                │
                ▼

             Agents
```

Agents assist.

Nexus decides.

---

# High-Level Agent Architecture

```
                      User
                        │
                        ▼

                ┌──────────────┐
                │    Nexus     │
                │ Orchestrator │
                └──────┬───────┘
                       │
                       ▼

          ┌──────────────────────────┐
          │      Agent Router        │
          └──────────┬───────────────┘
                     │
  ┌──────────────────┼──────────────────┐
  │                  │                  │
  ▼                  ▼                  ▼
```

Research Agent    Planning Agent    Execution Agent

```
  │                  │                  │

  └──────────────────┼──────────────────┘
                     │
                     ▼

               Shared Memory
```

---

# Agent Taxonomy

Nexus uses specialized agents.

Each agent has one responsibility.

No agent should become a general-purpose autonomous system.

---

# Agent Type 1

Research Agent

Purpose:

Information gathering.

Responsibilities:

* AI news collection
* Paper collection
* Technology tracking
* Competitive intelligence
* Knowledge extraction

Inputs:

Research requests

Outputs:

Structured findings

Reports

Summaries

The Research Agent never executes actions.

---

# Agent Type 2

Planning Agent

Purpose:

Reasoning and decomposition.

Responsibilities:

* Break tasks into steps
* Create plans
* Estimate complexity
* Suggest workflows

Inputs:

Goals

Tasks

Requests

Outputs:

Plans

Recommendations

Checklists

The Planning Agent never executes actions.

---

# Agent Type 3

Execution Agent

Purpose:

Perform approved work.

Responsibilities:

* Generate code
* Refactor code
* Create documentation
* Analyze repositories

Possible Runtimes:

Gemini CLI

Claude Code

Future:

OpenHands

Aider

Codex

Execution agents operate only after approval.

---

# Agent Type 4

Communication Agent

Purpose:

Human-facing messaging.

Responsibilities:

* Email generation
* Summary generation
* Notification formatting
* Report formatting

Inputs:

Events

Results

Outputs:

Messages

Digests

Reports

The Communication Agent never changes state.

---

# Agent Type 5

Memory Agent

Purpose:

Memory retrieval.

Responsibilities:

* Context retrieval
* Historical lookup
* State reconstruction
* Timeline generation

Inputs:

Queries

Outputs:

Relevant context

Memory Agent never modifies memory directly.

---

# Shared Memory Architecture

All agents share a common memory system.

No agent owns memory.

Architecture:

```
         ┌─────────────────┐
         │ Shared Memory   │
         └────────┬────────┘
                  │

  ┌───────────────┼───────────────┐
  │               │               │
```

Research       Planning      Execution

```
  │               │               │

  └───────────────┼───────────────┘

                  │

              Nexus
```

Benefits:

Single source of truth.

Consistent context.

Auditability.

Recoverability.

---

# Memory Categories

Nexus memory contains:

Task Memory

Approval Memory

Execution Memory

Research Memory

Communication Memory

User Preference Memory

System Event Memory

Every memory item must:

* Persist
* Be queryable
* Be auditable

---

# Agent Router

Purpose:

Select the correct agent.

Architecture:

```
           Request
               │
               ▼

         Agent Router
               │

  ┌────────────┼────────────┐

  ▼            ▼            ▼
```

Research     Planning     Execution

Routing is deterministic.

Routing should not rely on an LLM.

Rule-based routing is preferred.

---

# LLM Usage Policy

LLMs are reasoning engines.

Not orchestration engines.

Permitted:

Research

Summarization

Planning

Drafting

Classification

Forbidden:

Approvals

State mutation

Execution authorization

Governance decisions

Workflow ownership

Nexus owns those responsibilities.

---

# Model Abstraction

All agents use a common model layer.

Architecture:

```
       Agent
         │
         ▼

  Model Interface
         │
         ▼

  OpenRouter Layer
         │
         ▼

     Providers

         │

┌────────┼────────┐

▼        ▼        ▼
```

Nemotron OwlAlpha DeepSeek

Agents never interact with providers directly.

---

# Agent Context Model

Every agent receives:

System Context

Task Context

Relevant Memory

Execution Constraints

Current Objective

Example:

{
task_id: "...",
objective: "...",
memory: [...],
constraints: [...],
user_preferences: [...]
}

Agents should never receive raw system state.

Only required context.

---

# Agent Lifecycle

```
             Created
                 │
                 ▼

             Assigned
                 │
                 ▼

             Executing
                 │

      ┌──────────┼──────────┐

      ▼                     ▼

  Success                Failure

      │                     │

      ▼                     ▼

  Archived             Retry Queue
```

All lifecycle transitions must be persisted.

---

# Execution Agent Design

Execution Agents are unique.

They interact with repositories.

Architecture:

```
        Approval Granted
                │
                ▼

       Execution Request
                │
                ▼

        Execution Agent
                │
                ▼

         Agent Runner
                │
                ▼

      Gemini / Claude

                │
                ▼

            Result
```

Execution Agents never bypass approval workflows.

---

# Overnight Autonomous Mode

Nexus may operate autonomously.

Allowed:

Research

Monitoring

Summarization

Reporting

Reminder Generation

Not Allowed:

Repository Mutation

Deployment

External Actions

without approval.

Autonomy should be constrained.

---

# Pi Integration Evaluation

Before implementing custom orchestration:

Evaluate:

https://github.com/earendil-works/pi

Questions:

Can Pi provide:

* Workflow execution?
* Agent lifecycle management?
* Runtime coordination?
* State management?

If Pi satisfies requirements:

Prefer integration.

If not:

Document limitations.

Proceed with custom implementation.

---

# Failure Handling

Agent failures are expected.

Recovery Strategy:

Agent Failure
↓
Retry Policy
↓
Fallback Model
↓
Escalation

No failure should terminate Nexus.

Agents are replaceable.

Nexus is not.

---

# Observability

Every agent interaction must generate events.

Examples:

Research Started

Research Completed

Plan Generated

Execution Started

Execution Completed

Execution Failed

Context Retrieved

Summary Generated

All events should be stored.

---

# Future Evolution

Current Model:

Single Orchestrator

Multiple Specialized Agents

Shared Memory

Deterministic Routing

Future Model:

Hierarchical Agents

Dynamic Agent Registration

Distributed Execution

Advanced Memory Systems

Multi-User Workspaces

These are future enhancements.

Not MVP requirements.

---

# Final Principle

Nexus is the operating system.

Agents are applications.

Memory is the source of truth.

Governance is mandatory.

Execution is controlled.

Reasoning is delegated.

The orchestrator remains authoritative at all times.
