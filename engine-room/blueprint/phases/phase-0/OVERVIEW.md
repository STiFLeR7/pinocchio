# Phase 0 — Project Foundation

Status: ✅ Complete
Start Date: 2026-06-19
Target Completion: 2026-06-19
Actual Completion: 2026-06-19

---

## Goal

Create a production-ready project skeleton that proves the system can boot, test, and run — before any orchestration logic exists.

## Philosophy

Every line of code written in Phase 0 will live forever in the codebase. Set high standards from day one.

## Deliverables

- [x] Repository structure and directory layout
- [x] Python project setup (pyproject.toml, all dependencies)
- [x] Configuration system (Pydantic Settings, YAML)
- [x] Structured logging framework (structlog)
- [x] Database setup (SQLAlchemy 2.0 async + SQLite + Alembic)
- [x] Testing framework (pytest, async support, factories)
- [x] Docker setup (Dockerfile, docker-compose)
- [x] CI pipeline (GitHub Actions)
- [x] Repository registry (config/repositories.yaml)
- [x] FastAPI skeleton (health check, startup, shutdown lifecycle)

## Action Points

| AP | Title | Status |
|---|---|---|
| AP-001 | Repository structure | ✅ |
| AP-002 | Python project (pyproject.toml) | ✅ |
| AP-003 | Configuration system | ✅ |
| AP-004 | Structured logging | ✅ |
| AP-005 | Database setup + migrations | ✅ |
| AP-006 | Testing framework | ✅ |
| AP-007 | Docker setup | ✅ |
| AP-008 | CI pipeline | ✅ |
| AP-009 | Repository registry | ✅ |
| AP-010 | FastAPI skeleton | ✅ |

## Exit Criteria

- [x] `python -m nexus` boots without errors
- [x] `pytest` runs and all tests pass
- [x] Database initializes with Alembic migrations
- [x] GitHub Actions CI passes on push
- [x] `docker-compose up` starts the application
- [x] `docs/` and `blueprint/` are populated

## Decisions Made

See `blueprint/DECISIONS/` for all ADRs recorded during this phase:
- **ADR-006**: Approved Tech Stack (Python 3.12+, uv, FastAPI, SQLAlchemy 2.x, SQLite, structlog, pytest, MyPy, Ruff)
- **ADR-007**: Gmail SMTP initial email provider with EmailProvider interface abstraction
- **ADR-008**: Discord User ID enforcement for approvals (owner governance)
- **ADR-009**: 24h approval expiration with review queue migration
- **ADR-010**: Task/runner timeouts (Research: 15m, Gemini: 30m, Claude: 45m, Hard limit: 60m)
- **ADR-011**: Local-first deployment model with containerized MVP

## Implementation Notes

- Cleaned up redundant `src/` directory from alternative builder agents to maintain package resolution consistency under the root `nexus/` package.
- Solved dynamic runtime import resolution conflicts with SQLAlchemy 2.0 and Pydantic v2 annotations when using `from __future__ import annotations` and Ruff import sorting by restoring `uuid` and `datetime` imports to module runtime namespace.
- Resolved Ruff and MyPy strict mode configuration issues to achieve 100% type safety and lint compliance.

## Blockers

None. All 8 open questions resolved.
