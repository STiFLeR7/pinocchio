# R-05 — Shared Resolution: Nexus File-Tool Host Bypass (v1.1.0)

> **Cross-track (H ∩ S) · Design only.** The **single** authoritative resolution for R-05 — owned once,
> referenced by both tracks, never duplicated. No code. Source: `../v1.0.1/sandbox-risk-register.md`
> (R-05) ≡ `../v1.0.1/nexus-gap-analysis.md` (Gap 7).

---

## 1. The shared risk

| | |
|---|---|
| **Risk** | Nexus `read_file`/`write_file` touch the **host filesystem directly**, bypassing the sandbox entirely — arbitrary host file read/write regardless of provider. |
| **Evidence** | `nexus.py:88-105` (raw `open()/read()/write()`, no `SandboxManager`, no path check). |
| **Appears in** | A-006 risk register as **R-05 (High)**; AP-105 gap analysis as **Gap 7 (🟡→ High when combined)**. Same defect, two audits. |

## 2. Ownership (no duplicate solutions)

| Concern | Owner | Consumer |
|---|---|---|
| The **containment/path-confinement boundary** (the mechanism) | **Track S** (`S-1-runtime-containment-design.md`) | — |
| **File tools routed through the boundary** (the adoption) | **Track H** (`H-1-nexus-tooling-design.md`) | Track S boundary |
| Network egress decision for real search | **Track S** policy, recorded here §6 | Track H search |

**Rule:** the boundary is designed and built **once** in Track S; Nexus does **not** invent its own
confinement (Rule 9, no hidden coupling). This document is the only place the resolution is specified.

## 3. Resolution strategy (design-level)

1. **Always-on floor — workspace path-confinement.** File tools resolve and validate every path against
   the approved workspace (`ExecutionRecord.repository` cwd). Any path resolving **outside** the
   workspace ⇒ **fail closed** (error result, audited). This holds for *every* provider, including
   local-first setups without Docker (ADR-011 friendly).
2. **Stronger ceiling — in-container file I/O when Docker is active.** When the active provider is
   Docker, file operations occur within the container's mounted `/workspace` (consistent with how
   `execute_command` already runs, `provider.py:154-159`), inheriting the filesystem policy
   (`readonly`/`restricted`).
3. **Least privilege.** Default workspace toward read-only unless the run legitimately requires writes
   (security-policy-design §3); writes confined to the workspace.

This is a **single mechanism** (a confinement seam at the sandbox boundary) with two enforcement
strengths (floor + ceiling) — not two separate solutions.

## 4. Architecture preservation

- File tools converge on the **same single chokepoint** as command execution (Rule 9).
- No new tables, no schema change (path validation is logic at the boundary).
- Governance/approval unchanged (Rule 5); audit records confinement + refusals (Rule 4).

## 5. Implementation order (cross-track dependency)

```
   S-2 (default-secure + fail-closed resolution)
        │
        ▼
   S-3 (enforced policy + startup validation)
        │
        ▼
   S-4 ── builds the confinement SEAM (boundary mechanism)  ◀── R-05 boundary lands here
        │
        ▼
   H-5 ── Nexus file tools ADOPT the seam                  ◀── R-05 closed here
```

**Order rule:** the Track S confinement seam (S-4) **must precede** Nexus file-tool adoption (H-5).
H-2…H-4 (honesty, search, lifecycle, resume) do **not** depend on R-05 and may proceed in parallel; only
the *file-tool* portion of Nexus Pilot is gated on S-4.

## 6. Search egress sub-decision (one answer for both tracks)

Real `web_search` (Track H) does network I/O. **Decision:** under a `network=none` container policy,
search runs as an **explicit control-plane-governed action** (host network), audited, **or** is disabled
— it is **never** a hidden in-container egress. If an operator wants in-container search, they must
select a provider/policy that explicitly permits egress (an audited choice). This is recorded **here**
so Tracks H and S do not diverge.

## 7. Definition of done (R-05)

- Nexus file tools cannot read/write outside the approved workspace (floor), verified by tests.
- With Docker active, file I/O is in-container (ceiling).
- Out-of-workspace access fails closed + audited.
- One mechanism, referenced by both `H-1-nexus-tooling-design.md` and
  `S-1-runtime-containment-design.md` — no duplicate implementation.

Closing R-05 is a **Pilot** requirement for **both** Nexus (Pilot) and Sandbox (Pilot Safe).
