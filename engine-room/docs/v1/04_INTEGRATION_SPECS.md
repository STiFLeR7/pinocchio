# 04_INTEGRATION_SPECS.md

# Nexus Integration Specifications

Version: 0.1

Status: Source of Truth

Project: Nexus

---

# Purpose

This document defines every external integration supported by Nexus.

It serves as the contract between:

* Nexus Core
* Communication Channels
* Agent Runtimes
* External APIs
* Future Services

All integrations must conform to these specifications.

No integration should directly mutate Nexus state.

All integrations communicate through the Event Gateway.

---

# Integration Principles

Every integration must satisfy:

* Idempotency
* Auditability
* Observability
* Recoverability
* Retryability

Integrations are adapters.

They are not business logic containers.

---

# Integration Architecture

```
                          External World
                                  │
                                  ▼
```

┌──────────────────────────────────────────────────────────────┐
│                      Integration Layer                       │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│ Discord │ Email │ WhatsApp │ OpenRouter │ Gemini │ Claude   │
│                                                              │
└─────────────────────────────┬────────────────────────────────┘
│
▼

┌──────────────────────────────────────────────────────────────┐
│                       Event Gateway                          │
└─────────────────────────────┬────────────────────────────────┘
│
▼

┌──────────────────────────────────────────────────────────────┐
│                        Nexus Core                            │
└──────────────────────────────────────────────────────────────┘

All communication flows through the Event Gateway.

No exceptions.

---

# Discord Integration

Status:

MVP Required

Priority:

Critical

Library:

discord.py

Purpose:

Primary operational interface.

Discord functions as the human control surface for Nexus.

---

# Discord Channel Structure

Required Channels:

# inbox

Incoming requests.

# tasks

Task creation and tracking.

# approvals

Approval requests.

# execution-log

Execution status updates.

# research

Research findings.

# summaries

Daily summaries.

# alerts

Failures and escalation events.

---

# Discord Event Flow

User Message
↓
Discord Adapter
↓
Event Gateway
↓
Nexus Event
↓
Task Engine

Responses follow the reverse path.

---

# Approval Workflow

Example:

Task:

Deploy report to client

↓

Approval Required

↓

Discord Approval Card

↓

User Approves

↓

Approval Event

↓

Execution Queue

Approval data must persist.

Approval state must survive restart.

---

# Discord Embed Standard

Approval Embed

Required Fields:

Approval ID

Task ID

Requester

Execution Type

Repository

Created Timestamp

Status

Actions:

Approve

Reject

All approval actions must generate audit events.

---

# Discord Failure Handling

Required Recovery:

Message Failure

↓

Retry

Permission Failure

↓

Alert

Rate Limit

↓

Backoff

Gateway Disconnect

↓

Reconnect

No approval should be lost.

---

# Email Integration

Status:

MVP Required

Priority:

High

Purpose:

Formal communication channel.

Email is used for:

* Daily summaries
* Notifications
* Alerts
* Research digests
* Approval notifications

---

# Email Categories

Daily Summary

Research Digest

Execution Report

Failure Alert

Reminder

Approval Notification

Every category must have a dedicated template.

---

# Email Template Directory

templates/email/

Required Files:

daily_summary.html

research_digest.html

approval_request.html

execution_report.html

failure_alert.html

reminder.html

---

# Email Event Flow

Nexus Event
↓
Email Service
↓
Template Renderer
↓
SMTP Provider
↓
Recipient

---

# Email Delivery Guarantees

Required:

Retry

Logging

Failure Tracking

Audit Events

Every email send attempt must be recorded.

---

# WhatsApp Integration

Status:

Future

Not MVP

Reason:

Additional operational complexity.

---

# Future Provider

Meta WhatsApp Cloud API

Potential Uses:

* Notifications
* Mobile approvals
* Reminders

Current Recommendation:

Focus on Discord and Email.

---

# OpenRouter Integration

Status:

MVP Required

Priority:

Critical

Purpose:

Unified LLM access layer.

OpenRouter acts as:

Model Gateway

Provider Router

Fallback Layer

---

# OpenRouter Responsibilities

Request Routing

Model Selection

Provider Abstraction

Fallback Routing

Usage Monitoring

Rate Limit Handling

---

# OpenRouter Flow

Agent Request
↓
Model Router
↓
OpenRouter
↓
Provider
↓
Response

No component should call providers directly.

---

# Model Priority

Tier 1

Nemotron

Tier 2

OwlAlpha

Tier 3

DeepSeek

Future

Qwen

Llama

Additional Models

---

# Fallback Policy

Nemotron Failure
↓
OwlAlpha

OwlAlpha Failure
↓
DeepSeek

DeepSeek Failure
↓
Escalation

All failures must be logged.

---

# Circuit Breaker Policy

Trigger Conditions:

429

Timeout

Provider Failure

Repeated Errors

Response:

Temporary Provider Suspension

Automatic Recovery Attempts

---

# Gemini CLI Integration

Status:

MVP Required

Priority:

Critical

Purpose:

Primary execution runtime.

Gemini performs:

Code Generation

Refactoring

Architecture Work

Documentation

Repository Tasks

---

# Gemini Execution Flow

Approved Task
↓
Execution Queue
↓
Gemini Runner
↓
Repository
↓
Output
↓
Execution Record

Gemini never receives direct user messages.

Only structured execution requests.

---

# Gemini Execution Contract

Input:

Task

Repository

Execution Context

Constraints

Expected Deliverable

Output:

Result

Logs

Artifacts

Exit Status

Execution Metadata

---

# Gemini Safety Rules

Allowed:

Approved Repository

Approved Task

Structured Context

Forbidden:

Arbitrary Shell Commands

Unapproved Repositories

Untracked Execution

Every execution must be auditable.

---

# Claude Code Integration

Status:

MVP Required

Priority:

Critical

Purpose:

Advanced engineering execution runtime.

Claude Code should implement the same execution contract as Gemini.

The execution layer should not know which runtime it is calling.

---

# Runtime Abstraction

Approved Task
↓
Execution Engine
↓
Runtime Adapter
↓
Gemini OR Claude

This allows runtime replacement.

---

# Repository Integration

Status:

MVP Required

Purpose:

Controlled execution environments.

Repositories are execution targets.

---

# Repository Registry

Required File:

config/repositories.yaml

Example:

repositories:

nexus:
path: D:/projects/nexus

memex:
path: D:/projects/memex

fosterx:
path: D:/projects/fosterx

Only registered repositories may execute.

---

# Git Integration

Purpose:

Track repository changes.

Capabilities:

Status

Commit

Push

Branch Information

Diff Collection

Future:

Pull Request Generation

---

# Git Safety Requirements

No repository mutation without approval.

All commits must be recorded.

All pushes must be recorded.

Execution history must reference commit hashes.

---

# Scheduler Integration

Status:

MVP Required

Provider:

APScheduler

Responsibilities:

Daily Summaries

Research Jobs

Reminders

Escalations

Cleanup Jobs

---

# Scheduler Flow

Scheduled Trigger
↓
Event Gateway
↓
Task Creation
↓
Workflow Execution

Scheduled jobs should behave like user-created tasks.

---

# Memory Integration

Status:

MVP Required

Purpose:

Persistent state storage.

Memory is not optional.

---

# Memory Responsibilities

Task Storage

Approval Storage

Execution Storage

Research Storage

Communication Storage

Audit Storage

Preferences Storage

---

# Memory Guarantees

Durability

Queryability

Recoverability

Auditability

No integration should maintain private state.

All state belongs to Nexus.

---

# Logging Integration

Status:

Mandatory

Every integration must emit:

Request Event

Success Event

Failure Event

Retry Event

Audit Event

Logging is required for:

Debugging

Monitoring

Compliance

Recovery

---

# Future Integrations

The architecture should support:

Slack

Microsoft Teams

Google Calendar

GitHub

Linear

Jira

Notion

Google Drive

GitLab

OpenHands

Aider

Codex

without architectural modification.

---

# Integration Governance Rules

Integrations are replaceable.

Business logic is not.

No integration should contain orchestration logic.

No integration should own state.

No integration should bypass approvals.

No integration should bypass the Event Gateway.

No integration should directly control execution.

---

# Final Principle

Integrations are gateways.

Nexus is the authority.

Memory is the source of truth.

Approvals govern execution.

All external systems are adapters around the Nexus Core.
