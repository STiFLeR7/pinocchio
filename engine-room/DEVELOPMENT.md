# Nexus — Development Guide

> **This file covers Nexus v1** (`nexus/`). For the released v2 platform (`nexus_*` packages), see
> [docs/development/DEVELOPMENT.md](docs/development/DEVELOPMENT.md) instead — it uses `uv`/`make`,
> not `pip`/`venv`. See [docs/README.md](docs/README.md) if you're not sure which applies to you.

> This guide is for active contributors and covers daily development workflows.
> Read [CONTRIBUTING.md](CONTRIBUTING.md) first.

---

## Prerequisites

| Tool | Version | Notes |
|---|---|---|
| Python | 3.11+ | Required |
| pip | Latest | Dependency management |
| Git | Any | Source control |
| Docker | Latest | Container support |
| Docker Compose | v2+ | Local environment |

Optional:
- VS Code with Python extension
- PyCharm Professional

---

## Initial Setup

```bash
# 1. Clone the repository
git clone https://github.com/hill-patel/nexus.git
cd nexus

# 2. Create a virtual environment
python -m venv .venv

# Windows (PowerShell)
.venv\Scripts\Activate.ps1

# Linux/macOS
source .venv/bin/activate

# 3. Install all dependencies (including dev tools)
pip install -e ".[dev]"

# 4. Copy and configure settings
cp config/settings.example.yaml config/settings.yaml
# Edit config/settings.yaml with your credentials

# 5. Initialize the database
alembic upgrade head

# 6. Verify setup
pytest tests/unit/
python -m nexus --health-check
```

---

## Configuration

All configuration is managed through:

1. `config/settings.yaml` — Local overrides (gitignored)
2. Environment variables — Override any setting
3. `config/settings.example.yaml` — Template (committed)

### Required Configuration

```yaml
# Discord
discord:
  token: "your-bot-token"
  guild_id: 123456789
  channels:
    inbox: "inbox"
    tasks: "tasks"
    approvals: "approvals"
    execution_log: "execution-log"
    research: "research"
    summaries: "summaries"
    alerts: "alerts"

# Email
email:
  smtp_host: "smtp.example.com"
  smtp_port: 587
  username: "nexus@example.com"
  password: "..."
  from_address: "nexus@example.com"
  to_address: "hill@example.com"

# OpenRouter
openrouter:
  api_key: "sk-or-..."
  primary_model: "nvidia/nemotron-..."
  fallback_models:
    - "owlalpha/..."
    - "deepseek/..."

# Database
database:
  url: "sqlite+aiosqlite:///./data/nexus.db"

# Repositories (allow-list)
# See config/repositories.yaml
```

### Repository Registry

Edit `config/repositories.yaml` to register allowed repositories:

```yaml
repositories:
  nexus:
    path: "D:/projects/nexus"
    description: "Nexus orchestration control plane"
  memex:
    path: "D:/projects/memex"
    description: "Memory system"
  fosterx:
    path: "D:/projects/fosterx"
    description: "FosterX project"
```

**Only registered repositories may be executed against.**

---

## Running the Application

### Development Mode

```bash
# Standard run
python -m nexus

# With hot reload (if uvicorn is used)
uvicorn nexus.api:app --reload --host 0.0.0.0 --port 8000
```

### Docker Mode

```bash
# Build image
docker-compose build

# Start all services
docker-compose up

# Start in background
docker-compose up -d

# Stop
docker-compose down
```

---

## Testing

### Running Tests

```bash
# All tests
pytest

# Unit tests only
pytest tests/unit/

# Integration tests only
pytest tests/integration/

# End-to-end tests
pytest tests/e2e/

# Specific test file
pytest tests/unit/test_task_engine.py

# With coverage
pytest --cov=nexus --cov-report=html

# Open coverage report
# Windows
start htmlcov/index.html
```

### Writing Tests

Every new component needs tests in all three layers:

```
tests/
├── unit/                   # Test components in isolation
│   ├── core/
│   │   ├── test_task_engine.py
│   │   ├── test_approval_engine.py
│   │   └── test_agent_router.py
│   ├── memory/
│   └── ...
├── integration/            # Test with real dependencies
│   ├── test_discord_adapter.py
│   ├── test_email_service.py
│   └── ...
└── e2e/                    # Full workflow tests
    ├── test_approval_workflow.py
    └── test_research_workflow.py
```

Test file conventions:

```python
# tests/unit/core/test_task_engine.py
import pytest
from nexus.core.task_engine import TaskEngine
from nexus.memory.models import TaskStatus

class TestTaskEngine:
    """Unit tests for TaskEngine."""

    def test_task_creation_persists_to_memory(self, task_engine, mock_memory):
        """Task creation must persist state immediately."""
        task = task_engine.create_task(title="Test Task", priority=1)
        assert mock_memory.was_saved(task.id)

    def test_task_lifecycle_transitions(self, task_engine):
        """All lifecycle transitions must be audited."""
        task = task_engine.create_task(title="Test")
        assert task.status == TaskStatus.CREATED
        task_engine.queue(task)
        assert task.status == TaskStatus.QUEUED
```

---

## Database Migrations

```bash
# Apply all pending migrations
alembic upgrade head

# Create a new migration (after changing models)
alembic revision --autogenerate -m "add workflow_checkpoints table"

# Rollback one migration
alembic downgrade -1

# View migration history
alembic history

# View current migration
alembic current
```

---

## Logging

All logging uses structlog. Never use `print()` or bare `logging`.

```python
import structlog
log = structlog.get_logger(__name__)

# Always include:
# - component name
# - correlation_id (from request context)
# - task_id (when applicable)

log.info("task.created", task_id=task.id, component="task_engine")
log.error("execution.failed", task_id=task.id, error=str(e), component="execution_engine")
log.debug("approval.routing", approval_id=approval.id, channel="approvals")
```

---

## Git Workflow

```bash
# Start work on a new AP
git checkout -b feat/phase-0-ap001-repository-structure

# After implementation and tests pass
git add -A
git commit -m "feat(foundation): initialize repository structure per ADR-001"

# Push and create PR
git push origin feat/phase-0-ap001-repository-structure
```

### Commit Message Format

```text
<type>(<scope>): <description>

Types: feat, fix, test, docs, refactor, chore
Scopes: foundation, task, approval, execution, memory, discord, email, router, scheduler
```

---

## IDE Setup

### VS Code (Recommended)

Install extensions:
- Python (Microsoft)
- Pylance
- Ruff (linting)
- SQLite Viewer

Recommended settings (`.vscode/settings.json`):

```json
{
  "python.defaultInterpreterPath": ".venv/Scripts/python.exe",
  "editor.formatOnSave": true,
  "[python]": {
    "editor.defaultFormatter": "charliermarsh.ruff"
  }
}
```

---

## Troubleshooting

### Database Locked Error

```bash
# SQLite WAL mode should prevent this. If it occurs:
# 1. Stop all running Nexus processes
# 2. Check for lingering file locks
# 3. If needed: rm nexus.db-wal nexus.db-shm
```

### Discord Bot Not Connecting

```bash
# Check:
# 1. Token is valid in config/settings.yaml
# 2. Bot has correct permissions (Send Messages, Read Message History, Add Reactions)
# 3. Bot is in the correct server
```

### OpenRouter Request Failures

```bash
# Check:
# 1. API key is valid
# 2. Model names are correct
# 3. Check circuit breaker state in logs
```
