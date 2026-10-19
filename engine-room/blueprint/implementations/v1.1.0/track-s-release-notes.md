# Track S Release Notes — Default-Secure Sandbox (v1.1.0 "Containment")

> Concise, audience-facing notes for the Track S sandbox-hardening increment. Track S is the first
> completed track of the v1.1.0 "Containment" line; the v1.1.0 release itself remains open pending
> Track H. Documentation-only artifact.

---

## Headline

**The execution sandbox is now default-secure.** It refuses to run on the host implicitly, validates
itself at startup, tells the truth about what it enforces, and confines agent file tools to the
approved workspace. Maturity: **Experimental → Pilot Safe**.

## Highlights

- **Fail-closed by default (S-2).** Disabled sandboxing or an unrecognized provider name now **refuses
  to execute** instead of silently falling back to the host. Closes R-01, R-02 (both Critical).
- **Boot-time validation (S-3).** Startup aborts on an incoherent sandbox config or an unavailable
  policy-enforcing provider; Docker availability is probed at boot, not discovered at first command.
  Closes R-06, R-07.
- **Honest enforcement (S-3).** Every execution records whether the provider actually enforces the
  policy (`policy_enforced`); a host run is **declared**, never pretended. Ends the "decorative policy."
  Closes R-03.
- **Workspace-confined file tools (S-4).** Nexus `read_file`/`write_file` are confined to the approved
  workspace; path traversal, absolute-path, and symlink escapes fail closed — provider-independent.
  Closes R-05 (the cross-track Nexus file-bypass).

## Security classification

| | |
|---|---|
| Before | **Unsafe By Default** / Experimental |
| After | **Pilot Safe** (`ADR-sandbox-pilot-safe`) |
| Critical risks open | **0** (R-01, R-02 eliminated) |
| Pilot-gating risks open | **0** (R-01/R-02/R-03/R-05/R-06/R-07 closed) |

## Operator guidance

- **Pilot use:** safe for supervised, single-operator pilots under the default config — it now refuses
  unsafe execution rather than running on the host.
- **Isolation (untrusted workloads):** set `sandbox.enabled=true`, `sandbox.provider=docker` (Docker
  installed and running), and ideally `filesystem_policy=readonly`. Startup will abort if Docker is
  unavailable.
- **Deliberate host execution:** `provider=local` is still allowed but is loudly warned at startup and
  audited per-execution (`policy_enforced=false`).
- **Audit:** command lifecycle events carry the `policy_enforced` flag; file-tool denials appear in the
  agent trajectory naming the workspace and "fail-closed".

## Known limitations (residual, disclosed)

- **R-04** — the command blacklist is a bypassable substring match (governance-owned; not closed here).
- **R-08** — commands run via a shell string surface (design-inherent; bounded under Docker).
- **R-09** — the default Docker mount is `restricted`, not `readonly` (`:ro` available; tighten for
  stricter pilots).
- In-container file I/O is deferred defense-in-depth; the host-side workspace floor already prevents
  escape.

**These keep the classification at Pilot Safe, not Production Safe.**

## Compatibility / impact

- **No behavior change** to CLI runtimes (Gemini/Claude), scheduler, governance, memory, events, schema,
  or migrations. No new features.
- Full suite **178 passed**; ruff + mypy clean; **zero regressions** across the track.
- Config defaults unchanged (`sandbox.enabled` still defaults `False`) — the change is that a disabled
  sandbox now **fails closed** instead of running on the host.

## Verification

| Gate | Result |
|---|---|
| Tests | 178 passed (project venv) |
| Lint | ruff — all checks passed |
| Types | mypy — no issues, 58 files |

## Status

Track S is **complete and frozen for commit**. The maturity upgrade is effective on commit to
`v1.1.0-planning`. Track H (Nexus evolution) is unaffected and not started.
