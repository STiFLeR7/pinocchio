# Repository Structure Layout

This document outlines the directory structure of the **Nexus Control Plane** repository. To keep import paths simple and ensure compatibility with Hatch/Hatchling packaging, the primary python package is placed in `nexus/` at the root of the repository, rather than nesting it under a redundant `src/` directory.

---

## Directory Tree

```
D:\nexus\
├── .github/                  # GitHub workflows configurations
│   └── workflows/
│       └── ci.yml            # CI test runner pipeline
├── alembic/                  # Database migration scripts
│   ├── versions/             # Revisions folder (untracked gitkeeps)
│   ├── env.py                # Alembic async env bootstrapper
│   └── script.py.mako        # Migration templates
├── blueprint/                # Living memory system
│   ├── DECISIONS/            # ADR decision records
│   ├── architecture/         # Runtime & systems blueprints
│   ├── phases/               # Phase breakdowns & task trackers
│   └── reports/              # Core evaluation reports
├── config/                   # Configuration files
│   ├── settings.example.yaml # Reference configurations template
│   └── repositories.yaml     # Allowlist repository paths registry
├── docker/                   # Docker setups
│   ├── Dockerfile            # Container build stages
│   └── docker-compose.yml    # Development runner compose file
├── docs/                     # Source-of-truth project documentation
├── nexus/                    # Core codebase package
│   ├── __init__.py           # Package version definition
│   ├── __main__.py           # Entry point uvicorn loader
│   ├── api.py                # FastAPI lifecycle, routes, router mapping
│   ├── config.py             # Pydantic Settings yaml parser
│   ├── database.py           # SQLite connection pools, session maker
│   ├── logging_config.py     # structlog JSON logger setup
│   ├── core/                 # Shared base primitives
│   │   ├── __init__.py
│   │   ├── exceptions.py     # Exceptions hierarchy
│   │   ├── events.py         # Base Pydantic events envelope
│   │   └── types.py          # Str-Enums (TaskStatus, EventType, Priority)
│   ├── gateway/              # Event dispatching gateways
│   ├── communication/        # External chat/alerts integrations
│   │   ├── discord/          # Discord bot embedding commands
│   │   └── email/            # Gmail SMTP wrappers
│   ├── intelligence/         # LLM prompt/routing logic (OpenRouter client)
│   ├── memory/               # Storage DB Models and Schemas
│   │   ├── __init__.py
│   │   ├── models.py         # SQLAlchemy ORM schemas mapping
│   │   └── schemas.py        # Pydantic V2 validation schemas
│   ├── execution/            # Subprocess execution runtimes
│   │   └── runners/          # Gemini CLI, Claude Code runner files
│   ├── agents/               # Autonomous planning/planning loop code
│   └── scheduling/           # Background scheduling tasks (APScheduler)
├── scripts/                  # Helper utilities and migration tools
├── templates/                # Email templates HTML layout
├── tests/                    # Core test suites
│   ├── conftest.py           # Database transaction test fixtures
│   ├── integration/          # System-integration tests
│   ├── e2e/                  # End-to-end user tests
│   └── unit/                 # Structural unit tests
│       ├── core/             # Types, exceptions, and events tests
│       └── memory/           # Database schema mapping models tests
├── alembic.ini               # Alembic migrations configuration
├── pyproject.toml            # Dependencies and hatchling build setup
├── ruff.toml                 # Ruff formatting and lint rules
└── uv.lock                   # Pinned dependency locks
```
