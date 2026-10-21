# S-1 — Sandbox Boundary Model (v1.1.0)

> **Track S · Design only.** The to-be containment/trust boundary, evolving the v1.0.1 as-is map
> (`../v1.0.1/sandbox-boundary-analysis.md`) from "boundary is opt-in" to "boundary is default and
> guaranteed." No code. Answers Q1 (default path) and supports Q5 (enforcement).

---

## 1. Trust zones

| Zone | Contents | Trust |
|---|---|---|
| **Control plane (host)** | FastAPI, DB (SQLite/WAL), Discord, scheduler, orchestrator, governance, memory, audit | Trusted |
| **Contained execution** | Approved commands + agent file/command tools | **Untrusted by default** |

The invariant v1.1.0 establishes: **untrusted execution must not run in the trusted zone unless the
operator explicitly and audibly chooses it.**

## 2. As-is vs to-be

| Property | As-is (v1.0.1) | To-be (v1.1.0 Pilot Safe) |
|---|---|---|
| Default provider | Local → host shell (`provider.py:96`) | Isolation-required; Docker if available, else fail closed |
| Unknown provider | Local/host (fail-open, `manager.py:52-53`) | **Raise** (fail closed) |
| Policy under Local | decorative (ignored) | Local = explicit-unsafe-opt-in only; otherwise policy **enforced or refused** |
| Host execution | silent default | deliberate, audited, opt-in (`provider=host-unsafe` or equiv.) |
| Agent file tools | host FS bypass (`nexus.py:88-105`) | confined to workspace (R-05) |
| Startup posture | no validation | fail-fast on unsafe/incoherent config |
| Audit | complete ✅ | complete (unchanged) |

## 3. To-be boundary map

```
            ┌──────────────────── CONTROL PLANE (trusted host) ─────────────────────┐
 approved   │  Approval gate ─▶ Governance(11-gate) ─▶ SandboxManager.execute()      │
 command /  │                                              │                          │
 agent tool │                          ┌── resolve (fail-closed) ──┐                  │
            │                          │                           │                  │
            │             provider=docker (default if avail)   provider=host-unsafe   │
            │                          │                        (explicit + audited)  │
            │                          ▼                           │                  │
            └──────────────────────────┼───────────────────────────┼──────────────────┘
                                        ▼                           ▼
                     ┌─── CONTAINER (enforced boundary) ──┐   ┌─ HOST (no boundary) ─┐
                     │ cpus/memory/network=none/-v ws[:ro]│   │ acknowledged unsafe   │
                     │ command + confined file I/O (R-05) │   │ loud audit + warning  │
                     └─────────────────────────────────────┘   └───────────────────────┘
                            ▲ unknown provider / missing Docker / unenforceable policy ─► FAIL CLOSED
```

## 4. What crosses the boundary, and where it is enforced

| Crossing | Boundary owner | Enforcement point |
|---|---|---|
| `execute_command` (all runtimes) | SandboxManager → Docker provider | `provider.py` (kept) |
| Nexus `read_file`/`write_file` | SandboxManager containment (R-05) | new confinement seam (Track S), consumed by Track H |
| Search egress (Nexus, real) | network policy of active provider | container `--network` / control-plane governed (R-05 §network) |
| Workspace FS | filesystem policy | volume mount, default toward `readonly` where feasible |

## 5. Default-path decision (Q1) and the ADR-011 tension

ADR-011 is **local-first** (Docker may be absent). The boundary model resolves this **without** a silent
host fallback:

- **Docker present** → default to Docker containment.
- **Docker absent** → **fail closed** for governed command execution; the operator must *explicitly*
  select an acknowledged host-unsafe mode (distinct, named provider) which emits a **loud startup +
  per-execution audit**. Host execution is thus never silent and never the unmarked default.
- This preserves local-first usability (operator can still opt into host) while making the **default
  safe** and the unsafe choice **visible and audited** (Rules 4 — audit; 9 — no hidden path).

## 6. Architecture preservation

- Single chokepoint reused (`SandboxManager.execute`) — no new execution route (Rule 9).
- Governance/approval precede the boundary unchanged (Rule 5).
- Audit ledger records boundary selection + unsafe-mode usage (Rule 4).
- No scheduler/memory/event change (Rules 3, 6, 7).

## 7. Tier mapping

Default-secure boundary + fail-closed crossings + confined file tools = **Pilot Safe**. Production-Safe
hardening (profiles, rootless, egress filtering) is deferred (master §7/Q8).
