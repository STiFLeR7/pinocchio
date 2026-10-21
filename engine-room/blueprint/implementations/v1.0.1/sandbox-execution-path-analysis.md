# Sandbox Execution Path Analysis (A-006)

> Exact trace of how a command reaches an OS process, for every provider and every runtime, with the
> precise conditions that select host vs. container execution. Audit-only.

---

## 1. The single chokepoint

All three runtimes execute external commands through one method — `SandboxManager.execute(...)`:

- **Gemini:** `gemini.py:105-108` → `SandboxManager(self.session, self.settings).execute(...)`
- **Claude:** `claude.py:100-103` → same
- **Nexus** (`execute_command` tool): `nexus.py:116-125` → same

So provider resolution in `SandboxManager` governs containment for **all** command execution. (Caveat:
Nexus `read_file`/`write_file` do **not** go through the manager — they touch the host FS directly,
`nexus.py:88-105`.)

## 2. Provider resolution — the decision table

`SandboxManager._resolve_provider()` (`manager.py:34-53`):

| Condition (in order) | Provider returned | Isolation |
|---|---|---|
| `settings` is not a `NexusSettings` | **Local** (`:37-38`) | ❌ host |
| `settings.sandbox` falsy | **Local** (`:40-41`) | ❌ host |
| `cfg.enabled == False` | **Local** (`:44-45`) | ❌ host |
| `provider == "docker"` | Docker (`:48-49`) | ✅ container |
| `provider == "mock"` | Mock (`:50-51`) | n/a (test) |
| **anything else** (incl. `"local"`, typos, unknown) | **Local** (`:52-53`) | ❌ host |

**The shipped default** is `enabled=False` (`config.py:135`) → the **3rd row** → **Local → host**.

## 3. What "Local" actually does

`LocalSandboxProvider.spawn` (`provider.py:88-101`):

```python
proc = await asyncio.create_subprocess_shell(command, stdout=PIPE, stderr=PIPE, cwd=cwd)
```

- Runs the **full command string through the host shell**, in the repository working directory.
- The `SandboxPolicy` (cpu/memory/network/filesystem/image) is built and **audited** in the manager
  (`manager.py:91-110`) but **never passed to or honored by** the Local provider. It is **decorative**.
- Result: no resource caps, full host network, full host filesystem, host user privileges.

## 4. What "Docker" actually does

`DockerSandboxProvider.spawn` (`provider.py:133-175`): real `docker run --name … --rm -i --cpus … --memory …
--network none -v <cwd>:/workspace[:ro] -w /workspace <image> sh -c "<command>"`. This **does** enforce
CPU, memory, network, and filesystem policy. Containment here is genuine — **but only reached when
`enabled=True` and `provider=="docker"`.**

## 5. The required questions — answered with evidence

1. **Default execution path?** Host. `enabled=False` → Local → `create_subprocess_shell` (`config.py:135`,
   `manager.py:44-45`, `provider.py:96`).
2. **When does host execution occur?** Whenever provider resolves to Local: default-disabled,
   non-`NexusSettings`, no sandbox config, `provider="local"`, **or any unrecognized provider name**
   (`manager.py:37-53`).
3. **Can unknown provider names trigger host execution?** **Yes.** The `else` branch returns Local
   (`manager.py:52-53`). A typo (`"dcoker"`, `"container"`, `"Docker "`) silently runs on host.
4. **Does Docker failure fail closed or open?** **Closed at the manager.** A Docker spawn error is
   audited and re-raised with **no host fallback** (`manager.py:172-179`); the command does not run on
   host. *However* there is **no Docker availability precheck** (`#13`), so failures surface only at
   spawn time. (The fail-**open** is in resolution/default, not in Docker error handling.)
5. **Is sandboxing enabled by default?** **No.** `SandboxConfig.enabled = False` (`config.py:135`).
6. **Which runtimes pass through the sandbox?** All three command paths (Gemini/Claude/Nexus
   `execute_command`) call `SandboxManager` — but under default they all land on Local/host. Nexus
   `read_file`/`write_file` bypass the manager entirely.
7. **Can any runtime bypass containment?** **Yes** — (a) all runtimes "bypass" via the default Local
   path; (b) Nexus file tools bypass the manager outright (`nexus.py:88-105`).
8. **Protections against arbitrary host execution?** Approval gate (human), repository allow-list +
   branch checks (`governance.py:495-548`), a 4-pattern substring command blacklist
   (`governance.py:616-641`, `policy_defaults.py:9`), and the control-plane health gate. Audit logging
   records every sandbox event (`audit.py`).
9. **Protections missing?** Default isolation; honoring policy under Local; fail-closed on unknown
   provider; Docker availability + sandbox startup validation; robust (non-substring) command policy;
   agent file-path confinement.
10. **Real security classification?** **Unsafe By Default** (see `sandbox-safety-review.md` §verdict).

## 6. Audit reality (a genuine strength)

Every execution emits immutable audit rows — `sandbox.created` (with full policy + command),
`sandbox.started`, then `sandbox.terminated`/`sandbox.timeout`/`sandbox.failure`
(`manager.py:101-179`, `audit.py:27-40`, `component="sandbox_manager"`). So host execution is **fully
observable after the fact**, even though it is **not contained** by default.
