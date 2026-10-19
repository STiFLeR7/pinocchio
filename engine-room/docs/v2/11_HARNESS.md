# Harness

Status: Target Architecture

---

# Purpose

The Harness is the standardized integration boundary of Nexus.

Every external capability connects to Nexus through a Harness.

A Harness provides a consistent operational interface regardless of implementation details.

Execution runtimes, context providers, validators, knowledge systems, communication channels, and future capabilities should all integrate using Harnesses.

---

# Why Harnesses Exist

Every external system behaves differently.

Examples

Claude Code

Gemini CLI

GitHub

Filesystem

Slack

Calendar

Google Drive

Search

Each exposes different APIs.

Different capabilities.

Different failure modes.

Without Harnesses, these implementation details spread throughout the platform.

Harnesses isolate those differences.

---

# Design Principles

## Standard Interface

Every Harness should expose a common operational contract.

Nexus should never need to understand provider-specific implementations.

---

## Capability Oriented

Harnesses expose capabilities.

Never implementations.

The platform asks

"What capabilities exist?"

Not

"What API is available?"

---

## Replaceable

Any Harness should be replaceable without affecting higher architectural layers.

Replacing Claude with Gemini should never affect Planning.

Replacing GitHub with GitLab should never affect Context Engineering.

---

## Observable

Every Harness should expose

- health
- metrics
- operational events
- failures
- latency
- capability availability

---

## Recoverable

Harnesses should expose recoverable operational failures.

Internal implementation details remain encapsulated.

---

# Harness Categories

---

## Runtime Harness

Provides execution capability.

Examples

- Claude Code
- Gemini CLI
- Nexus Agent
- Browser Agent
- Local Shell
- Human Operator

---

## Context Harness

Provides operational context.

Examples

- Repository
- Filesystem
- Calendar
- Email
- Slack
- Drive
- Documentation
- Research Sources

---

## Knowledge Harness

Provides knowledge retrieval.

Examples

- Operational Knowledge
- Repository Knowledge
- Organization Knowledge
- Historical Knowledge

---

## Validation Harness

Provides independent validation.

Examples

- Test Runner
- Linter
- Static Analysis
- Build System
- Security Scanner
- Review System

---

## Communication Harness

Provides communication capabilities.

Examples

- Email
- Slack
- Discord
- Teams
- SMS
- Notifications

---

## Governance Harness

Provides approval and policy enforcement.

Examples

- Human Approval
- Policy Engine
- Security Rules
- Access Control

---

## Observability Harness

Provides operational visibility.

Examples

- Logs
- Metrics
- Traces
- Events
- Dashboards

---

# Common Harness Contract

Every Harness should expose

Identity

Capabilities

Availability

Health

Configuration

Authentication

Operations

Events

Errors

Metrics

Version

The contract remains consistent regardless of implementation.

---

# Harness Lifecycle

```
Registered

↓

Configured

↓

Available

↓

Executing

↓

Monitoring

↓

Completed
```

Failure path

```
Available

↓

Failure

↓

Recovery

↓

Available
```

---

# Harness Registration

Every Harness should register

Identity

Supported Capabilities

Version

Configuration Schema

Operational Constraints

Health Endpoints

Supported Operations

Registration enables discovery.

---

# Capability Discovery

Planning and Orchestration should discover capabilities dynamically.

Example

```
Need

↓

Research Capability

↓

Search Registry

↓

Available Harnesses

↓

Execution Strategy
```

Planning should reason about capabilities.

Never implementations.

---

# Harness Health

Every Harness should expose

Healthy

Unavailable

Degraded

Initializing

Maintenance

Unknown

Operational health should be continuously observable.

---

# Failure Model

Harnesses report

Unavailable

Authentication Failure

Timeout

Configuration Error

Resource Exhausted

Internal Error

Failures should expose standardized operational information.

---

# Harness Events

Examples

Registered

Started

Stopped

Capability Changed

Health Changed

Failure

Recovered

Events integrate with Supervision.

---

# Architectural Boundaries

Harnesses

✓ expose capabilities

✓ standardize integration

✓ isolate implementation

✓ expose operational health

✓ emit events

Harnesses never

✗ perform planning

✗ understand goals

✗ perform orchestration

✗ create Work Packages

Harnesses remain infrastructure.

---

# Future Evolution

Future versions may support

- dynamic capability negotiation

- distributed harnesses

- remote harnesses

- sandboxed harnesses

- capability composition

- organization-wide harness registry

The architectural principles remain unchanged.

---

# North Star

Harnesses isolate implementation from capability.

Nexus coordinates capabilities.

Harnesses expose them.

Every external system integrates through a common operational boundary.