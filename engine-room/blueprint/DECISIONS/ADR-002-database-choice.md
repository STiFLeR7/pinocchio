# ADR-002: Database Choice and Migration Path

Date: 2026-06-19
Status: Accepted (Per Documentation)

---

## Context

Nexus requires persistent state storage for:
- Tasks, Approvals, Executions, Research (Operational Memory)
- Knowledge items (Knowledge Memory)
- System events, audit log, checkpoints (System Memory)

The system must survive restarts without state loss (Critical Constraint 2, 10).

---

## Decision

### Phase 1 (MVP — v0.1)

**SQLite with WAL Mode**

Rationale:
- Zero-dependency embedded database
- Sufficient for single-user operation
- WAL mode enables concurrent reads + one writer
- Explicitly referenced in architecture docs and memory architecture
- Easy to backup (single file)

Configuration:
```python
# SQLAlchemy engine configuration for SQLite
SQLALCHEMY_DATABASE_URL = "sqlite+aiosqlite:///./nexus.db"
engine = create_async_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={
        "check_same_thread": False,
        "timeout": 20,
    },
    echo=False,
)

# Enable WAL mode on connection
@event.listens_for(engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()
```

### Phase 2 (v0.5+)

**PostgreSQL**

Rationale:
- Concurrent writers
- Better performance under load
- Production-grade reliability
- Required for future multi-user support

Migration Path:
- Alembic handles schema migrations
- SQLAlchemy 2.0 async abstracts the difference
- Environment variable switches the connection string

---

## Data Model Overview

All tables must include:
- `id` — UUID primary key
- `created_at` — UTC timestamp (immutable)
- `updated_at` — UTC timestamp
- `is_archived` — soft delete (never hard delete)

Core tables:
- `tasks`
- `task_events` (append-only audit log)
- `approvals`
- `approval_events` (append-only)
- `executions`
- `execution_events` (append-only)
- `research_items`
- `knowledge_items`
- `system_events` (append-only, immutable)
- `audit_log` (immutable)
- `workflow_checkpoints`
- `scheduled_jobs`
- `notifications`

---

## Consequences

**Positive:**
- Alembic migrations provide version control for schema
- SQLite WAL mode handles APScheduler + Discord + request concurrency at MVP scale
- Clean path to PostgreSQL without application code changes

**Negative:**
- SQLite cannot handle truly concurrent writes at high volume
- Must enforce single-writer patterns in async code

---

## Status

Accepted — consistent with documentation specifications.
