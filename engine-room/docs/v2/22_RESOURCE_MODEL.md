# Resource Model

Status: Target Architecture

---

# Purpose

The Resource Model defines every allocatable entity that may participate in operational execution within Nexus.

Resources represent the operational assets available to the platform.

Planning identifies required resources.

Orchestration allocates resources.

Execution consumes resources.

Supervision observes resources.

Recovery restores resource availability.

---

# Why Resources Exist

Operational work requires resources.

Examples include

- AI runtimes
- Human operators
- Repositories
- Filesystems
- APIs
- Compute
- Storage
- Documents
- External systems

Without a unified Resource Model, every subsystem would manage resources differently.

The Resource Model provides a common representation across the platform.

---

# Design Principles

## Uniform Representation

Every resource should expose a common operational interface.

Planning should not distinguish between

Claude Code

GitHub

Filesystem

Calendar

Human Operator

They are all Resources.

---

## Capability Based

Resources advertise capabilities.

They never advertise implementation details.

---

## Observable

Every resource exposes

- health
- availability
- utilization
- operational metrics

---

## Allocatable

Resources are assigned to Work Packages.

Assignments are temporary.

Resources remain independent.

---

## Replaceable

Equivalent resources should be interchangeable whenever capabilities allow.

---

# Resource Lifecycle

```
Discovered

↓

Registered

↓

Available

↓

Allocated

↓

In Use

↓

Released

↓

Available
```

Failure Path

```
Allocated

↓

Unavailable

↓

Recovery

↓

Available
```

---

# Resource Categories

## Human Resources

Examples

Operator

Reviewer

Architect

Approver

Developer

---

## AI Resources

Examples

Claude Code

Gemini CLI

Codex

Nexus Agent

Browser Agent

---

## Workspace Resources

Examples

Git Repository

Filesystem

Database

Cloud Storage

Shared Drive

---

## Communication Resources

Examples

Slack

Discord

Email

Teams

SMS

---

## Infrastructure Resources

Examples

Docker

Kubernetes

Cloud APIs

Terminal

VM

Container

---

## Knowledge Resources

Examples

Knowledge Base

Memory

Research Repository

Documentation

Architecture Library

---

## Compute Resources

Examples

CPU

GPU

RAM

Storage

Network

---

# Resource Structure

Every Resource contains

Identity

Type

Capabilities

Status

Availability

Owner

Configuration

Constraints

Health

Version

Metadata

---

# Resource Availability

Possible states

Available

Busy

Reserved

Offline

Maintenance

Failed

Unknown

Availability changes dynamically.

---

# Resource Allocation

Resources are allocated by Orchestration.

Planning may request

```
Need

↓

Repository Editing

↓

Capability

↓

Available Resources

↓

Allocation
```

Planning never allocates resources.

---

# Resource Constraints

Examples

Concurrency Limits

Execution Limits

Security Restrictions

Budget Limits

Time Windows

Workspace Permissions

Operational Policies

Constraints influence allocation.

---

# Resource Health

Every resource exposes

Health

Latency

Availability

Utilization

Failure Count

Operational Metrics

These metrics support supervision.

---

# Resource Utilization

Examples

CPU Usage

GPU Usage

Memory Usage

API Rate Limits

Concurrent Sessions

Execution Time

Resource utilization supports operational optimization.

---

# Resource Relationships

Resources may depend upon

Other Resources

Examples

Claude Code

↓

Filesystem

↓

Git Repository

↓

Network

Relationships remain explicit.

---

# Resource Registry

Every Resource registers

Identifier

Capabilities

Configuration

Status

Health

Owner

Operational Limits

Supported Operations

The registry supports discovery.

---

# Resource Discovery

Planning discovers required capabilities.

Orchestration discovers available resources.

Resource discovery remains implementation independent.

---

# Resource Scheduling

Orchestration may

Allocate

Reserve

Release

Reassign

Suspend

Restore

Scheduling decisions should remain observable.

---

# Relationship with Capabilities

Capabilities describe

What can be done.

Resources describe

Who or what can do it.

---

# Relationship with Harness

Harnesses expose Resources.

Resources remain implementation independent.

---

# Relationship with Runtime

Runtime is one category of Resource.

Not every Resource is a Runtime.

---

# Architectural Boundaries

Resource Model

✓ defines allocatable entities

✓ defines allocation

✓ defines availability

✓ defines health

✓ supports discovery

✓ supports scheduling

Resource Model never

✗ performs execution

✗ creates plans

✗ validates execution

✗ performs governance

---

# Future Evolution

Future versions may support

- distributed resource pools

- elastic resource allocation

- predictive scheduling

- organization-wide resource catalogs

- cost-aware allocation

These enhancements should preserve resource independence.

---

# North Star

Resources represent the operational assets available to Nexus.

Capabilities describe what is possible.

Resources determine what is currently available.

Operational intelligence depends on allocating the right resource at the right time.