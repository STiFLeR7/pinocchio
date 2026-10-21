# ADR-001: Technology Stack

Date: 2026-06-19
Status: Proposed (Pending Owner Confirmation)
Proposed By: Initial Analysis

---

## Context

Nexus requires a production-quality technology stack for:
- The orchestration control plane (API server)
- Persistent state storage
- Structured logging
- Task scheduling
- Discord integration
- Email delivery
- LLM interaction
- Testing
- Containerization

Decisions here have long-term architectural implications because Nexus is designed for production operation, not prototyping.

---

## Decision

The following technology stack is proposed based on the docs, constrained by:
- Python ecosystem (implied throughout docs)
- Production-quality requirement (Constraint 26)
- Replaceability of integrations (Constraint 12)

### Core Runtime

| Component | Choice | Rationale |
|---|---|---|
| Language | Python 3.11+ | Strong async support, typing, ecosystem |
| API Framework | FastAPI | Async-native, Pydantic integration, OpenAPI |
| Validation | Pydantic v2 | Performance, strict typing, serialization |
| ORM | SQLAlchemy 2.0 (async) | Async support, migration path to Postgres |
| Migrations | Alembic | Paired with SQLAlchemy, robust |
| Database (MVP) | SQLite (WAL mode) | Zero-dependency, embedded, sufficient for single user |
| Database (v0.5+) | PostgreSQL | Concurrency, production readiness |

### Scheduling

| Component | Choice | Rationale |
|---|---|---|
| Scheduler | APScheduler 3.x | Explicitly specified in docs, persistent job store |

### Communication

| Component | Choice | Rationale |
|---|---|---|
| Discord | discord.py (py-cord or nextcord) | Explicitly specified in docs |
| Email | aiosmtplib + Jinja2 templates | Async, template-based as specified in docs |

### Intelligence

| Component | Choice | Rationale |
|---|---|---|
| LLM Gateway | OpenRouter (via httpx) | Explicitly specified in docs |
| HTTP Client | httpx (async) | Async-native, modern |

### Observability

| Component | Choice | Rationale |
|---|---|---|
| Logging | structlog | Explicitly specified in docs, structured JSON |

### Testing

| Component | Choice | Rationale |
|---|---|---|
| Test Runner | pytest | Explicitly specified in docs |
| Async Tests | pytest-asyncio | Required for async code |
| Factories | factory_boy | Test data factories |
| Mocking | pytest-mock + respx | HTTP mocking for OpenRouter |
| Coverage | pytest-cov | Coverage reporting |

### Infrastructure

| Component | Choice | Rationale |
|---|---|---|
| Containerization | Docker + docker-compose | Explicitly specified in docs |
| CI | GitHub Actions | Explicitly specified in docs |

---

## Consequences

**Positive:**
- All choices are well-established, production-proven libraries
- Async throughout enables non-blocking I/O for Discord, email, and LLM calls
- SQLAlchemy 2.0 async supports clean migration to PostgreSQL
- structlog provides machine-readable audit logs

**Negative:**
- SQLite has write concurrency limitations (mitigated by WAL mode)
- APScheduler job store needs to be configured for persistence
- discord.py library choice (py-cord vs nextcord) needs confirmation

---

## Open Questions

- GAP-004: Owner confirmation of this tech stack required
- Discord library variant (discord.py, py-cord, or nextcord)?
- Email provider choice?

---

## Status

Proposed — requires owner confirmation before Phase 0 begins.
