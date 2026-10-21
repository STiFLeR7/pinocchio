# Sandbox Boundary Analysis (A-006)

> Maps the **trust/containment boundary**: what is inside the contained zone, what is on the host, and
> exactly where the boundary is crossed (or absent). Separates audited reality from future hardening.
> Audit-only — no fixes proposed.

---

## 1. The intended boundary vs. the real boundary

**Intended (per `SandboxConfig` + Docker provider):** approved commands run inside a resource-capped,
network-isolated, filesystem-restricted container; the host is protected.

**Real (shipped default):** the boundary **does not exist** by default. `enabled=False` routes every
command to `LocalSandboxProvider`, which runs it in the host shell with full host privileges
(`manager.py:44-45`, `provider.py:96`). The containment boundary is **opt-in**, materializing only when
`enabled=True` **and** `provider="docker"` **and** Docker is present.

## 2. Boundary map

```
                         ┌─────────────────────── HOST (trusted control plane) ───────────────────────┐
                         │  FastAPI · DB(SQLite/WAL) · Discord · Scheduler · Orchestrator             │
                         │                                                                            │
   approved command ───▶ │  Governance(11-gate)  ──▶  SandboxManager._resolve_provider()             │
                         │     · allow-list        │                                                  │
                         │     · substring blacklist│        ┌── enabled=False / unknown ──▶ Local ──┐│
                         │     · health gate        │        │   (NO BOUNDARY — runs on host) ◀───────┘│
                         │                          └── docker ──▶ Docker provider                     │
                         │                                          │                                  │
                         └──────────────────────────────────────────┼──────────────────────────────────┘
                                                                     ▼
                                              ┌─── CONTAINER (only real boundary) ───┐
                                              │ --cpus --memory --network none       │
                                              │ -v cwd:/workspace[:ro]  image  sh -c │
                                              └──────────────────────────────────────┘
```

- **Inside the boundary (Docker only):** CPU/mem caps, no network, workspace-scoped FS.
- **On the host (default + fallbacks):** full network, full FS, host privileges, no caps.
- **Always on host (no boundary regardless of provider):** Nexus `read_file`/`write_file`
  (`nexus.py:88-105`).

## 3. Where the boundary is crossed / missing

| Crossing point | Boundary present? | Evidence |
|---|---|---|
| Gemini/Claude/Nexus command → `SandboxManager` | Conditional (Docker only) | `gemini.py:107`, `claude.py:102`, `nexus.py:117` |
| Manager → Local provider | **None** (host) | `manager.py:44-53`, `provider.py:96` |
| Manager → Docker provider | Real container boundary | `provider.py:133-175` |
| Unknown provider name | **None** (fails open to host) | `manager.py:52-53` |
| Docker spawn failure | Fail-closed (no host fallback) ✅ | `manager.py:172-179` |
| Nexus file tools | **None** (direct host FS) | `nexus.py:88-105` |
| Workspace volume (Docker) | Semi-permeable (rw unless `:ro`) | `provider.py:154-159`, `config.py:140` |

## 4. Defense-in-depth layers actually present (host case)

When isolation is off, the only barriers between an actor and the host are:
1. **Approval gate** — human must approve the execution (strong, but human-dependent).
2. **Repository allow-list + branch policy** — `governance.py:495-548` (scopes *where*, not *what*).
3. **Command blacklist** — `governance.py:616-641`, 4 substring patterns (weak; R-04).
4. **Health gate** — blocks execution if control plane unhealthy (`governance.py:83`).
5. **Audit log** — complete, immutable, after-the-fact (`audit.py`) — detection, not prevention.

There is **no preventive isolation layer** in this list — all are policy/observability, not containment.

## 5. Reality vs. roadmap boundary (scope guard)

**Reality (A-006 certifies):** containment is opt-in; default is host execution; Docker provider is the
only real boundary; resolution fails open on unknown provider; audit is strong.

**Roadmap (NOT this audit — future Action Point territory, descriptive only):** default-secure posture,
honoring policy under a restricted-local mode, fail-closed unknown-provider handling, Docker-availability
+ sandbox-startup validation, a non-substring command policy, and agent file-path confinement. A-006
**proposes none of these as work** — it only records that they are absent.

## 6. Dependency note

This boundary interacts with **AP-105 (Nexus)**: Nexus Gap 7 (unconfined file tools, no path
confinement) is the same `nexus.py:88-105` finding surfaced here as R-05 — a shared item across the two
audits, owned by neither alone.
