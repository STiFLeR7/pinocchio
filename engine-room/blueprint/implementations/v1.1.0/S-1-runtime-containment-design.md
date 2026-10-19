# S-1 — Runtime Containment Design (v1.1.0)

> **Track S · Design only.** How each runtime's execution is contained under the to-be model, including
> the Nexus file tools (R-05). No code. Answers Q5 (enforcement) and Q6 (Nexus file tools).

---

## 1. The single chokepoint (preserve)

All three runtimes already funnel external command execution through one method —
`SandboxManager.execute(...)`: Gemini (`gemini.py:107`), Claude (`claude.py:102`), Nexus
`execute_command` (`nexus.py:117`). **v1.1.0 keeps this single chokepoint** and makes containment a
property of the chokepoint, so hardening it once hardens all runtimes (Rule 9, no new paths).

## 2. Containment per runtime

| Runtime | Path | v1.1.0 containment |
|---|---|---|
| Gemini (`execute`) | `SandboxManager.execute` | Inherits default-secure provider + enforced policy automatically |
| Claude (`execute`) | `SandboxManager.execute` | Same — no runner-side change needed |
| Nexus `execute_command` | `SandboxManager.execute` | Same — inherits containment |
| Nexus `read_file`/`write_file` | **bypasses manager** (`nexus.py:88-105`) | **R-05** — must be brought under the boundary |
| Nexus `web_search` (real, Track H) | network I/O | Egress governed by active policy (§4) |

The only runtime path **outside** the chokepoint today is Nexus file I/O — the R-05 gap.

## 3. R-05 — bring Nexus file tools under the boundary (ownership + seam)

- **Ownership:** Track S owns the *containment seam*; Track H's file tools *consume* it. Single design
  in `R-05-shared-resolution.md` (not duplicated).
- **Seam options (design-level; concrete choice = impl AP):**
  1. **Workspace path-confinement** — file tools resolve/validate paths against the approved workspace
     (`ExecutionRecord.repository` cwd) and refuse paths outside it (a confinement check before host
     FS access). Works even in `host-unsafe` mode and in local-first setups without Docker.
  2. **In-container file ops** — when Docker is active, file I/O occurs inside the container's mounted
     `/workspace` (consistent with `execute_command`).
- **Design preference:** **path-confinement as the always-on floor** (option 1), with in-container
  semantics (option 2) when Docker is the active provider. This guarantees confinement regardless of
  provider while remaining local-first friendly (ADR-011).
- **Refusal:** any file path resolving outside the workspace ⇒ **fail closed** (error result), audited.

## 4. Search egress (cross-track with Track H)

Real `web_search` (Track H tooling-design) performs network I/O. Containment rule:

- Under a `network=none` container policy, in-container search egress is blocked; therefore search, when
  enabled, runs as a **control-plane-governed action** (host network) **or** is disabled — an explicit,
  audited choice, never a hidden egress (Rule 9).
- The decision (control-plane search vs. in-container egress allowance) is recorded in
  `R-05-shared-resolution.md` §network so both tracks share one answer.

## 5. Termination integration (cross-track with Track H)

Nexus cooperative cancellation (lifecycle-design) reuses the **existing** sandbox termination —
`SandboxProcess.terminate()` / provider terminate (`provider.py:45-48,187-207`) — to kill an in-flight
contained `execute_command`. No new termination mechanism is introduced in Track S; the capability
already exists and is simply *invoked* by the Nexus lifecycle.

## 6. Architecture preservation

- One chokepoint, one boundary, consumed by all runtimes (Rules 1, 2, 9).
- File-tool confinement is enforced at the boundary, not via runtime-specific reach-arounds (Rule 9).
- Governance/approval precede containment unchanged (Rule 5); audit records every containment + refusal
  (Rule 4); no scheduler/memory/event change (Rules 3, 6, 7).

## 7. Closes / addresses

R-05 (Nexus file bypass, shared) and the per-runtime enforcement half of R-01/R-03. Tier: **Pilot Safe**
(file confinement is also a Nexus **Pilot** requirement — single resolution serves both).
