# Nexus — Gaps, Risks, and Open Questions

Date: 2026-06-19
Last Updated: 2026-06-19 (all OQs resolved)
Author: Initial Analysis

---

## Purpose

This document tracks all identified gaps, risks, inconsistencies, and open questions discovered during documentation review and implementation.

New items are appended. Resolved items are marked but never deleted.

---

## Documentation Gaps

### GAP-001: docs/02_TECH_STACK.md Contains Duplicate Content

- **Severity:** Medium
- **Status:** Open
- **Category:** Documentation Defect

**Description:**
The file `docs/02_TECH_STACK.md` contains identical content to `docs/00_BRIEF.md`. The actual tech stack specification is missing.

**Expected Content:**
The tech stack document should specify:
- Python version (3.11+ is implied)
- FastAPI
- SQLAlchemy
- Pydantic v2
- SQLite → PostgreSQL migration path
- APScheduler
- discord.py
- structlog
- pytest
- Docker
- GitHub Actions
- Alembic

**Impact:** Missing canonical tech stack reference. Currently relying on scattered mentions in other docs.

**Resolution Needed:** Owner should provide or confirm the actual tech stack spec.

---

### GAP-002: docs/07_NEXUS_AGENT.md Has Wrong File Header

- **Severity:** Low
- **Status:** Open
- **Category:** Documentation Defect

**Description:**
The file `docs/07_NEXUS_AGENT.md` has its internal heading as `# 07_REFERENCES.md`, not `# 07_NEXUS_AGENT.md`. The filename and the content header are inconsistent.

**Impact:** Cosmetic — content appears to be the References document, not a Nexus-specific document.

**Resolution Needed:** Clarify whether the file should be named `07_REFERENCES.md` or if a separate `07_NEXUS_AGENT.md` is needed.

---

### GAP-003: docs/INITIAL_PROMPT.md Is a Duplicate

- **Severity:** Low
- **Status:** Open
- **Category:** Documentation Defect

**Description:**
`docs/INITIAL_PROMPT.md` contains identical content to `docs/08_MEMORY_ARCHITECTURE.md`.

**Impact:** Confusion about authoritative source. Could lead to divergence.

**Resolution Needed:** Clarify the purpose of `INITIAL_PROMPT.md`. If it is an agent initialization prompt, it should have distinct content. If it was an accidental copy, it should be removed or replaced.

---

### GAP-004: Actual Tech Stack Not Formally Specified in One Place

- **Severity:** Medium
- **Status:** Open
- **Category:** Missing Specification

**Description:**
Technology choices are scattered across multiple documents. There is no single, complete tech stack specification.

Technologies that are implied but never formally consolidated:
- Python version (3.11+ assumed from FastAPI usage)
- SQLAlchemy version (v1 or v2?)
- Pydantic version (v1 or v2 — critical difference)
- APScheduler version (v3 or v4?)
- discord.py version
- Email library choice (smtplib, aiosmtplib, or third-party like SendGrid?)
- SMTP provider vs. API provider (Mailgun, SendGrid, SES, etc.)

**Impact:** Could lead to incompatible library choices during Phase 0.

**Resolution Needed:** Owner to confirm or approve proposed tech stack.

---

## Architecture Gaps

### GAP-005: No Specification for Discord Bot Authentication

- **Severity:** High
- **Status:** Open
- **Category:** Missing Specification

**Description:**
The documents specify Discord as the primary interface but do not define:
- How the bot token is managed (env var, secrets manager, vault)
- How user identity is verified (only Hill Patel should be able to approve)
- How the bot handles DM vs. channel messages
- Whether approval buttons use Discord's interaction system or emoji reactions

**Impact:** Discord integration design cannot begin without resolving these.

**Resolution Needed:** Define authorization model for Discord interactions.

---

### GAP-006: No Specification for Email Provider

- **Severity:** Medium
- **Status:** Open
- **Category:** Missing Specification

**Description:**
Email integration is specified as MVP-required but the email provider is not defined:
- SMTP server (self-hosted, Gmail SMTP, Mailgun, SendGrid, AWS SES)?
- Authentication method (username/password, API key, OAuth)?
- Sending domain?

**Impact:** Cannot implement email integration without provider decision.

**Resolution Needed:** Owner to specify email provider.

---

### GAP-007: Approval Timeout/Expiration Behavior Not Fully Specified

- **Severity:** Medium
- **Status:** Open
- **Category:** Underspecified Behavior

**Description:**
The approval system mentions "Approval Expiration" (Phase 3, AP-305) but does not define:
- Default expiration time
- Behavior when approval expires (escalation? auto-reject? notify?)
- Whether expired approvals can be re-requested
- How the scheduler handles expiration checks

**Impact:** Approval state machine cannot be fully implemented.

**Resolution Needed:** Define approval expiration rules.

---

### GAP-008: Workflow Orchestrator Design Not Specified

- **Severity:** High
- **Status:** Open
- **Category:** Missing Specification

**Description:**
The Workflow Orchestrator is described as "the most important component" and "all workflows pass through the orchestrator," but there is no specification for:
- The internal workflow execution model (state machine? event-driven? saga pattern?)
- How workflows are persisted and recovered
- Checkpoint format
- How the orchestrator handles concurrent workflows
- Whether it is synchronous or async

This is the central component and its design is underspecified.

**Impact:** Core architectural ambiguity. Must be resolved before Phase 1.

**Resolution Needed:** Design the Workflow Orchestrator before Phase 1 begins. Should be informed by Pi evaluation.

---

### GAP-009: Pi Evaluation Is Mandatory But Sequencing Is Ambiguous

- **Severity:** High
- **Status:** Open
- **Category:** Execution Risk

**Description:**
Multiple documents mandate evaluating Pi (https://github.com/earendil-works/pi) before implementing orchestration primitives. However:
- Phase 8 is listed as the "Pi Evaluation" phase — but this comes AFTER Phase 1 (Core Infrastructure) which includes the Workflow Orchestrator
- If Pi is adopted, Phase 1 architecture could change significantly
- The sequencing creates a risk of building then replacing the orchestration layer

**Impact:** Phase 1 may need to be redesigned if Pi evaluation occurs after it.

**Resolution Needed:** Pi evaluation should occur in parallel with Phase 0, not Phase 8.

**Recommendation:** Run Pi evaluation as Phase 0 parallel track so findings inform Phase 1 design.

---

### GAP-010: Nexus Agent Investigation Not Completed

- **Severity:** Medium
- **Status:** Open
- **Category:** Missing Evaluation

**Description:**
The docs indicate Nexus Agent is installed locally and should be evaluated as an execution runtime before Phase 4. However:
- No Nexus evaluation has been completed
- Its CLI interface, execution model, configuration, and tool-calling capabilities are unknown
- The decision to use it as Primary Runtime, Secondary Runtime, Specialized Runtime, or Reject has not been made

**Impact:** Phase 4 (Execution Runtime) design depends on this decision.

**Resolution Needed:** Investigate Nexus Agent CLI and capabilities. Document findings in `blueprint/references/nexus-evaluation.md`.

---

### GAP-011: No CI/CD Environment Specified

- **Severity:** Medium
- **Status:** Open
- **Category:** Missing Specification

**Description:**
GitHub Actions is mentioned for CI. However:
- No branch protection rules are specified
- No deployment target is specified (local only? cloud?)
- No secrets management strategy is defined
- No container registry is specified (if Docker is used for deployment)

**Impact:** Phase 0 Docker/CI work needs clarity.

**Resolution Needed:** Define deployment model and CI expectations.

---

### GAP-012: No Specified Error Classification Taxonomy

- **Severity:** Low
- **Status:** Open
- **Category:** Missing Specification

**Description:**
The docs mention retry policies and failure recovery extensively but do not define:
- Error classification (transient vs. permanent failures)
- Retry limits per operation type
- Backoff strategies (exponential? linear?)
- Dead letter handling for permanently failed items

**Impact:** Retry implementation in Phase 7 will need to invent these classifications.

**Resolution Needed:** Define error taxonomy and retry parameters.

---

## Implementation Risks

### RISK-001: Monolith-to-Services Migration

- **Severity:** Medium
- **Category:** Architectural Risk

**Description:**
The architecture document specifies v0.1 as a monolith, v0.5 as modular services, and v1.0 as distributed. If the monolith is not designed with service boundaries from day one, migration will be painful.

**Mitigation:** Use clean module boundaries within the monolith. Avoid cross-module imports that bypass defined interfaces.

---

### RISK-002: SQLite Concurrency Limitations

- **Severity:** Medium
- **Category:** Technical Risk

**Description:**
SQLite has known limitations with concurrent writes. If APScheduler jobs, Discord events, and user requests all attempt concurrent writes, SQLite may cause bottlenecks or locking issues.

**Mitigation:** Use SQLite WAL mode. Ensure all database access goes through async SQLAlchemy sessions. Plan PostgreSQL migration in Phase 10.

---

### RISK-003: Discord Rate Limits During High Volume

- **Severity:** Medium
- **Category:** Integration Risk

**Description:**
Discord has strict rate limits. If multiple approval requests, notifications, and reports are sent simultaneously, rate limiting can cause message failures.

**Mitigation:** Implement message queue with backoff. Never send Discord messages in tight loops.

---

### RISK-004: Execution Timeout Management

- **Severity:** High
- **Category:** Execution Risk

**Description:**
Gemini CLI and Claude Code may run for extended periods. There is no specification for:
- Maximum execution time limits
- How Nexus handles a hung agent process
- Whether Nexus can cancel an execution in progress

**Mitigation needed:** Define execution timeout policy and cancellation protocol.

---

### RISK-005: Secret Management

- **Severity:** High
- **Category:** Security Risk

**Description:**
Nexus will hold multiple sensitive credentials (Discord token, OpenRouter API key, SMTP credentials). No secrets management strategy is defined.

**Mitigation needed:** Define secrets storage approach (environment variables, local secrets file, vault) before any credentials are written to config files.

---

## Open Questions Requiring Owner Input

| # | Question | Priority |
|---|---|---|
| OQ-001 | What is the complete, approved tech stack? | ✅ Resolved — ADR-006 |
| OQ-002 | What email provider should be used for MVP? | ✅ Resolved — ADR-007 (Gmail SMTP) |
| OQ-003 | What is the Discord bot authorization model? | ✅ Resolved — ADR-008 (User ID enforcement) |
| OQ-004 | What is the approval expiration time and behavior? | ✅ Resolved — ADR-009 (24h, notify, no auto-reject) |
| OQ-005 | Should Pi evaluation run before Phase 1? | ✅ Resolved — Yes, mandatory pre-Phase-1 |
| OQ-006 | Is there a deployment target beyond local? | ✅ Resolved — ADR-011 (Local-first MVP) |
| OQ-007 | What is the maximum execution timeout? | ✅ Resolved — ADR-010 (30/45/60 min) |
| OQ-008 | What secrets management approach? | ✅ Resolved — .env file (gitignored) for MVP |

---

## Resolved Items

| # | Item | Resolution | Date |
|---|---|---|---|
| OQ-001 | Tech stack | Python 3.12+, uv, FastAPI, SQLAlchemy 2.x, Pydantic v2, APScheduler, discord.py, structlog, pytest, Ruff, MyPy, Docker, GitHub Actions | 2026-06-19 |
| OQ-002 | Email provider | Gmail SMTP (MVP) with EmailProvider abstraction. Future: Resend, SES | 2026-06-19 |
| OQ-003 | Discord auth | User ID enforcement via OWNER_DISCORD_ID. Only owner may approve/reject | 2026-06-19 |
| OQ-004 | Approval expiration | 24h expiration → notify only, do not auto-reject, move to review queue | 2026-06-19 |
| OQ-005 | Pi evaluation | Mandatory before Phase 1. New order: Phase 0 → Pi Eval → Phase 1 | 2026-06-19 |
| OQ-006 | Deployment target | Local-first for MVP. Future: Oracle Cloud Free VM hybrid | 2026-06-19 |
| OQ-007 | Execution timeout | Research: 15m, Gemini: 30m, Claude: 45m, Hard limit: 60m | 2026-06-19 |
| OQ-008 | Secrets management | .env file (gitignored) for MVP | 2026-06-19 |

---

## Resolution Log

### 2026-06-19 — All Open Questions Resolved

Owner (Hill Patel) answered all 8 open questions.
ADR-006 through ADR-011 created to record decisions.
New Constraint 28 added: No execution may run indefinitely.
Phase 0 implementation authorized to begin.
