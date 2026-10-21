# RULES.md

## Project

Project Name: Nexus

Tagline:

AI Orchestration Control Plane for Human-Governed Autonomous Execution

---

# Mission

Nexus is not a chatbot.

Nexus is an orchestration system responsible for:

* Task management
* Approval workflows
* Agent execution
* Multi-channel communication
* Research automation
* Daily intelligence reporting
* State persistence
* Human governance

The system must operate as a reliable control plane rather than a conversational assistant.

Every architectural decision should prioritize:

1. Determinism
2. Reliability
3. Observability
4. Testability
5. Recoverability

over model intelligence.

---

# Execution Authority

Execution mode is autonomous.

The agent should not repeatedly ask for permission before performing implementation work.

Assume:

* File creation approved
* File modification approved
* Refactoring approved
* Dependency installation approved
* Test creation approved
* Documentation generation approved
* Git commits approved
* Git pushes approved

Continue until completion.

Exception:

If requirements are ambiguous, conflicting, incomplete, or could significantly alter system architecture, stop and ask precise questions.

Never guess.

---

# Mandatory Thinking Process

Before implementing any feature:

1. Understand requirements
2. Identify architectural implications
3. Identify dependencies
4. Identify failure modes
5. Identify testing requirements
6. Produce implementation plan
7. Execute

Never jump directly into coding.

---

# No Guessing Policy

Forbidden:

* Inventing requirements
* Assuming business logic
* Assuming workflows
* Assuming user intent
* Assuming infrastructure constraints

If information is missing:

Ask.

If information is unclear:

Ask.

If multiple valid architectures exist:

Present options and request clarification.

---

# State Over Stateless

Nexus must never be designed as a stateless chatbot.

All important interactions must persist state.

Examples:

* Tasks
* Approvals
* Research jobs
* Executions
* Summaries
* User preferences
* Communication history

Every workflow must be resumable after restart.

Design for recovery.

Design for persistence.

Design for auditability.

---

# Memory Requirements

Memory is a first-class system component.

Memory must be:

* Persistent
* Queryable
* Recoverable
* Versionable

System memory should support:

* Task history
* Approval history
* Execution history
* Research history
* Communication history

Memory must survive:

* Process restart
* Container restart
* Deployment replacement

---

# Architecture Requirements

Architecture must remain:

* Modular
* Service-oriented
* Testable
* Replaceable

All major components require clear boundaries.

Examples:

* Core Engine
* Agent Runtime
* Memory Layer
* Messaging Layer
* Execution Layer
* Scheduler
* Approval Engine

Avoid monolithic business logic.

---

# Visual Architecture Requirement

Whenever architecture is discussed:

ALWAYS invoke:

brainstorming:superpowers

and

visual-companion

skills.

All architecture discussions must include:

* System diagram
* Component diagram
* Data flow diagram
* Failure path diagram

Visual explanation is mandatory.

No architecture discussion should be text-only.

---

# Skill Utilization Policy

Always prefer available Gemini CLI skills before custom implementation.

Actively evaluate whether an existing skill can accelerate:

* Planning
* Architecture
* Visualization
* Refactoring
* Debugging
* Research
* Documentation

Mandatory skills:

* brainstorming:superpowers
* visual-companion

Use additional skills whenever beneficial.

Do not ignore available tooling.

---

# Pi Integration Consideration

Repository:

https://github.com/earendil-works/pi

Pi must be evaluated before implementing orchestration logic.

Determine whether Pi can provide:

* Agent orchestration
* Workflow execution
* Runtime coordination
* State management
* Agent lifecycle control

Avoid rebuilding capabilities already provided by Pi.

Document findings.

---

# Discord Standards

Discord is a primary operating interface.

Use dedicated channels.

Never use thread-based architecture.

Suggested channel structure:

# inbox

# tasks

# approvals

# execution-log

# research

# summaries

# alerts

Messages must be structured and machine-readable when appropriate.

Use embeds whenever possible.

Approval messages must be deterministic.

Approval state must persist.

---

# Email Standards

Email is an official communication channel.

All email generation must use reusable templates.

Required categories:

* Daily Summary
* Approval Request
* Execution Report
* Failure Alert
* Research Digest
* Reminder

Email formatting must remain professional and consistent.

---

# Execution Safety

Execution systems are high risk.

Never allow arbitrary command execution.

All execution targets must be allow-listed.

Execution requests must resolve to approved repositories.

All executions must generate:

* Start event
* Completion event
* Failure event

Execution history must be persisted.

---

# Model Routing

Models are replaceable infrastructure.

Never couple business logic to a specific model.

All model interaction must pass through an abstraction layer.

Required capabilities:

* Model fallback
* Retry handling
* Timeout handling
* Rate-limit handling
* Circuit breaking

---

# Testing Requirements

Every feature requires tests.

Required levels:

1. Unit Tests
2. Integration Tests
3. End-to-End Tests

No feature is complete without tests.

Testing is part of implementation.

Not a later task.

---

# Observability Requirements

All important actions must be observable.

Required:

* Structured logging
* Audit events
* Error tracking
* Execution tracking

The system should explain:

* What happened
* Why it happened
* What changed

without requiring code inspection.

---

# Git Workflow

Development workflow:

1. Implement
2. Test
3. Verify
4. Commit
5. Push

Commits should be meaningful.

Avoid generic commit messages.

Examples:

feat(approval): add discord approval workflow

fix(router): recover from OpenRouter rate limits

test(execution): add end-to-end execution coverage

---

# Quality Bar

Production-quality mindset is mandatory.

Prioritize:

Correctness > Features

Reliability > Speed

Architecture > Hacks

Maintainability > Shortcuts

Deterministic systems > Clever systems

Nexus is a control plane.

Build accordingly.
