# Sandbox Capability Ledger (A-006)

> Evidence-based classification of every sandbox/containment capability by **current repository
> reality only**. Audit-only; no code changed.
>
> **Subject:** `nexus/execution/sandbox/` (`manager.py`, `provider.py`, `audit.py`, `lifecycle.py`,
> `collector.py`) + `SandboxConfig` (`config.py:133-141`) + runtime call-sites.
> **States:** Implemented · Partially Implemented · Simulated · Stubbed · Experimental · Production Ready ·
> Not Present.

---

## Ledger

| # | Capability | State | Evidence | Notes |
|---|---|---|---|---|
| 1 | Provider abstraction (`SandboxProvider` ABC) | **Implemented** | `provider.py:57-79` (spawn/wait_and_capture/terminate) | Clean, replaceable contract |
| 2 | Local provider (host execution) | **Implemented** | `provider.py:82-124` — real `asyncio.create_subprocess_shell(command, cwd=cwd)` | **Runs directly on host; ignores all policy** |
| 3 | Docker provider | **Implemented** | `provider.py:127-207` — real `docker run --rm` with `--cpus`,`--memory`,`--network`,`-v ...:/workspace`,image | Genuinely isolates when used |
| 4 | Mock provider | **Implemented (test-only)** | `provider.py:210-252` — keyword-driven canned outputs | For unit tests |
| 5 | Provider resolution | **Partially Implemented** | `manager.py:34-53` | Resolves correctly **but fails open to Local** on disabled/unknown (see #11) |
| 6 | Default isolation | **Not Present** | `config.py:135` `enabled=False`; `manager.py:44-45` → `LocalSandboxProvider` | **Default = host execution, zero isolation** |
| 7 | CPU/memory limit enforcement | **Partially Implemented** | Enforced only in Docker (`provider.py:145-148`); `SandboxPolicy` computed + audited but **Local ignores it** (`provider.py:88-101`) | Decorative under default |
| 8 | Network isolation | **Partially Implemented** | Docker `--network none` (`provider.py:151-152`); Local = full host network | Decorative under default |
| 9 | Filesystem isolation | **Partially Implemented** | Docker volume mount/`:ro` (`provider.py:154-159`); Local = full host FS | Decorative under default |
| 10 | Sandbox audit logging | **Production Ready** | `audit.py:19-40` immutable `AuditLogRecord`; `manager.py:101-179` created/started/terminated/timeout/failure | Real, every lifecycle event |
| 11 | Fail-closed on unknown provider | **Not Present** | `manager.py:52-53` `else: return LocalSandboxProvider()` | **Unknown/typo provider → host execution (fail-open)** |
| 12 | Fail-closed on Docker spawn failure | **Implemented** | `manager.py:172-179` audits + `raise spawn_err`; no host fallback | Docker failure does **not** silently drop to host ✅ |
| 13 | Docker availability validation | **Not Present** | No precheck before resolving/using Docker provider | Misconfig surfaces only at spawn time |
| 14 | Startup / config validation of sandbox | **Not Present** | No sandbox checks in `api.py` lifespan; `_validate_startup_configuration` covers only owner IDs | No fail-fast on unsafe sandbox config |
| 15 | Container lifecycle (spawn/wait/terminate) | **Implemented** | `provider.py` (docker `kill`, `:187-207`); `lifecycle.py:cleanup_orphaned_sandboxes` | Real for Docker |
| 16 | Orphaned-sandbox cleanup | **Implemented** | `lifecycle.py:16 cleanup_orphaned_sandboxes` | Present (invocation/schedule not in A-006 scope) |
| 17 | Command safety guard (blacklist) | **Partially Implemented / Experimental** | `governance.py:616-641` substring `if pattern in command`; `policy_defaults.py:9` = 4 patterns | Bypassable substring match |
| 18 | Path confinement for agent file tools | **Not Present** | `nexus.py:88-105` raw host FS read/write (bypasses sandbox entirely) | Agent file I/O is uncontained |
| 19 | Resource collector / metrics | **Implemented** | `collector.py` present | Telemetry (not a containment control) |

---

## Roll-up by state

- **Production Ready (1):** audit logging.
- **Implemented (8):** provider ABC, local provider, docker provider, mock provider, docker
  fail-closed, container lifecycle, orphan cleanup, resource collector.
- **Partially Implemented (4):** provider resolution, CPU/mem limits, network isolation, FS isolation,
  command blacklist *(all conditional on Docker being enabled; inert under the default Local path)*.
- **Not Present (5):** default isolation, fail-closed-on-unknown-provider, docker availability
  validation, sandbox startup validation, agent file-path confinement.

## The decisive fact

Every containment control in this subsystem (#7, #8, #9, and effectively #17 for resource abuse) is
**real only inside the Docker provider**. Under the **shipped default** (`enabled=False` → Local) they
are computed, audited, and then **ignored** — commands execute on the host. Containment is therefore
**opt-in, not default**, and provider misconfiguration **fails open** to the host.

*All gaps are stated descriptively. A-006 proposes no fixes.*
