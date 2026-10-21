# ADR-011: Deployment — Local-First Architecture

Date: 2026-06-19
Status: Accepted
Decided By: Hill Patel

---

## Decision

Nexus MVP targets **local machine** as the primary deployment environment.

---

## Rationale

Nexus requires:
- Gemini CLI (local binary)
- Claude Code (local binary)
- Nexus Agent (local binary, already installed)
- Local Git repositories
- Local execution environments

Cloud cannot easily access these without significant infrastructure complexity.

---

## Local Deployment Model

```
Hill's Machine
    ├── nexus/ (this repository)
    ├── D:/projects/nexus
    ├── D:/projects/memex
    ├── D:/projects/fosterx
    ├── Gemini CLI (installed)
    ├── Claude Code (installed)
    └── Nexus Agent (installed)
```

---

## Future Architecture

```
Phase MVP: Local Machine
    │
    ▼
Phase v0.5: Oracle Cloud Free VM
    │       (for scheduled jobs, reports, Discord bot)
    │       Local machine for execution only
    ▼
Phase v1.0: Hybrid Local + Cloud
    │       Cloud: orchestration, memory, scheduling
    │       Local: execution agents, repositories
    ▼
Future: Full Cloud (if local binary constraint is removed)
```

---

## Implications for Phase 0

1. **Docker** is used for consistent local environment, not for production deployment
2. **GitHub Actions** is CI, not CD (no deployment pipeline needed for MVP)
3. **Database** lives locally at `D:/nexus/data/nexus.db`
4. **Config** lives locally at `config/settings.yaml` (gitignored)
5. Nexus runs as a long-lived process (not a cloud function)

---

## Status

Accepted — Owner approved 2026-06-19.
