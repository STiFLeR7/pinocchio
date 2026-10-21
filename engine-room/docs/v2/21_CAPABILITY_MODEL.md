# Capability Model

Status: Target Architecture

---

# Purpose

The Capability Model defines how operational functionality is represented throughout Nexus.

Capabilities describe **what can be accomplished**, independent of **who performs it** or **how it is implemented**.

Capabilities are one of the core architectural abstractions of Nexus.

Every subsystem reasons about capabilities rather than implementations.

---

# Why Capabilities Exist

Execution technologies evolve.

Providers change.

Skills evolve.

Tools appear and disappear.

Operational capabilities remain relatively stable.

Examples

Repository Analysis

Code Generation

Research

Planning

Documentation

Architecture Review

Validation

Communication

Scheduling

These capabilities may be provided by different runtimes over time.

---

# Architectural Position

```
Goal

↓

Planning

↓

Required Capabilities

↓

Capability Resolution

↓

Execution Strategy

↓

Harness

↓

Runtime
```

Planning reasons about capabilities.

Execution consumes implementations.

---

# Design Principles

## Capability First

Nexus should always reason about capabilities before selecting implementations.

---

## Runtime Independent

Capabilities must never reference

- vendors
- AI models
- APIs
- providers

---

## Reusable

A capability should be reusable across domains whenever possible.

---

## Composable

Multiple capabilities may combine to solve larger operational objectives.

---

## Observable

Capability usage should be measurable.

---

# Capability Definition

A Capability represents a reusable unit of operational functionality.

A Capability answers

> What operational outcome can be produced?

It never answers

> Which runtime performs it?

---

# Capability Structure

Every Capability contains

Identifier

Name

Description

Version

Category

Inputs

Outputs

Constraints

Dependencies

Metadata

---

# Capability Categories

Examples

## Analysis

Repository Analysis

Architecture Analysis

Root Cause Analysis

Research

Dependency Analysis

---

## Development

Code Generation

Refactoring

Testing

Debugging

Code Review

---

## Documentation

Documentation

Summarization

Specification Generation

Presentation Creation

---

## Communication

Email

Slack

Notification

Meeting Summary

Reporting

---

## Operations

Planning

Scheduling

Deployment

Validation

Monitoring

Recovery

---

## Knowledge

Retrieval

Reflection

Knowledge Capture

Pattern Discovery

---

# Capability Composition

Capabilities may be composed.

Example

```
Resolve Bug

↓

Repository Analysis

↓

Root Cause Analysis

↓

Implementation

↓

Testing

↓

Documentation
```

Each Capability contributes one operational function.

---

# Capability Discovery

Capabilities should be discoverable.

Discovery includes

Name

Category

Provider

Availability

Version

Operational Constraints

Discovery should remain implementation independent.

---

# Capability Resolution

Planning identifies

Required Capabilities.

Capability Resolution identifies

Available Providers.

Example

```
Need

↓

Research

↓

Capability Registry

↓

Available Providers

↓

Execution Strategy
```

---

# Capability Providers

Capabilities may be implemented by

Claude Code

Gemini CLI

Human Operator

Browser Agent

Shell

GitHub

Future Runtime

The Capability remains unchanged.

Only providers change.

---

# Capability Constraints

Capabilities may define

Required Context

Security Requirements

Governance Requirements

Resource Requirements

Validation Requirements

Execution Constraints

---

# Capability Versioning

Capabilities evolve independently.

Planning references capability versions.

Execution providers advertise supported versions.

---

# Capability Registry

The registry maintains

Identifier

Category

Version

Provider

Availability

Health

Dependencies

Metadata

The registry does not perform execution.

---

# Relationship with Skills

Skills describe

Operational procedures.

Capabilities describe

Operational functionality.

One Skill may require multiple Capabilities.

One Capability may support multiple Skills.

---

# Relationship with Harness

Harnesses expose Capabilities.

Harnesses do not create Capabilities.

---

# Relationship with Runtime

Runtimes implement Capabilities.

Runtimes never define Capabilities.

---

# Architectural Boundaries

Capability Model

✓ defines operational functionality

✓ supports discovery

✓ supports composition

✓ supports versioning

✓ supports provider independence

Capability Model never

✗ performs execution

✗ selects providers

✗ creates plans

✗ validates execution

---

# Future Evolution

Future versions may support

- capability negotiation

- capability marketplaces

- capability optimization

- learned capabilities

- organization-specific capabilities

These enhancements should preserve provider independence.

---

# North Star

Capabilities define what Nexus can accomplish.

Providers determine who performs the work.

Keeping these concerns separate allows Nexus to evolve independently from any execution technology.