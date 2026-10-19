# ADR-006: Approved Technology Stack (Final)

Date: 2026-06-19
Status: Accepted
Decided By: Hill Patel

Supersedes: ADR-001 (Proposed)

---

## Decision

The following technology stack is **approved** for Nexus v0.1 (MVP).

### Core Runtime

| Component | Choice | Version |
|---|---|---|
| Language | Python | 3.12+ |
| Package Manager | uv | Latest |
| API Framework | FastAPI | Latest |
| Validation | Pydantic | v2 |
| ORM | SQLAlchemy | 2.x (async) |
| Migrations | Alembic | Latest |
| Database (MVP) | SQLite | (WAL mode) |
| Database (Future) | PostgreSQL | Latest |

### Scheduling

| Component | Choice |
|---|---|
| Scheduler | APScheduler |

### Communication

| Component | Choice |
|---|---|
| Discord | discord.py |
| Email | Gmail SMTP (see ADR-007) |

### Intelligence

| Component | Choice |
|---|---|
| LLM Gateway | OpenRouter |

### Observability

| Component | Choice |
|---|---|
| Logging | structlog |

### Code Quality

| Component | Choice |
|---|---|
| Linting | Ruff |
| Type Checking | MyPy |

### Testing

| Component | Choice |
|---|---|
| Test Runner | pytest |
| Async | pytest-asyncio |
| HTTP Mocking | respx |
| Mocking | pytest-mock |
| Coverage | pytest-cov |

### Infrastructure

| Component | Choice |
|---|---|
| Containerization | Docker + docker-compose |
| CI | GitHub Actions |

---

## Notes

- `uv` replaces pip/poetry for package management — faster, reproducible
- `Ruff` replaces flake8/isort/black — single fast linter/formatter
- `MyPy` enforces strict type correctness across the codebase
- All database access through SQLAlchemy 2.x async sessions only

---

## Status

**Accepted** — Owner approved 2026-06-19.
