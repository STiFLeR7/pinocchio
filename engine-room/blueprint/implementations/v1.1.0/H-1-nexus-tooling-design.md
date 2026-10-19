# H-1 — Nexus Tooling Design (v1.1.0)

> **Track H · Design only.** The tool-execution model: a tool abstraction, the real `SearchProvider`,
> structured tool-calls, and the file-tool containment seam (shared R-05). Preserves runtime
> abstraction (Rule 2). No code. Answers Q4 (search) and the tooling half of Q1/Q3.

---

## 1. Problem (evidence)

- `web_search` is **canned** in both mock and real branches (`nexus.py:76-86`) — Cap 8 Simulated.
- Tool selection is parsed from free text with a heuristic fallback to `finish` (`nexus.py:213-234`) —
  Cap 3, Gap 6.
- File tools (`read_file`/`write_file`) touch the **host FS directly**, bypassing the sandbox
  (`nexus.py:88-105`) — Cap 5/6, **R-05** (shared with Track S).
- `execute_command` already routes through `SandboxManager` (`nexus.py:116-125`) — keep.

## 2. Tool model (conceptual)

Define a minimal **tool abstraction** so each tool is a uniform, testable unit — consistent with the
runtime registry/adapter philosophy (Rule 2), not a new framework:

```
ToolCall   = { thought: str, tool: ToolName, arguments: object }   # structured, validated
ToolResult = { ok: bool, output: str, error: str | null }          # honest result, feeds exit-status
ToolName   ∈ { web_search, read_file, write_file, execute_command, finish }   # NO new tools
```

- The model must emit a **structured `ToolCall`**; validation is explicit. A malformed/unparseable call
  is an explicit error → an error `ToolResult` and a real failure path (no silent `finish`, fixing
  Gap 6 / Cap 3).
- `ToolResult.ok=false` contributes to a **real exit status** (lifecycle-design), never always-`0`.

## 3. Search provider (Q4)

- Introduce a **`SearchProvider` port** (a small protocol: `search(query) -> results`), resolved like
  other runtime collaborators (constructor injection, as `openrouter_client` is today).
- **Production:** a real provider (e.g. an HTTP search/retrieval backend or the OpenRouter-backed
  research path already present in `intelligence/research.py`). The concrete provider choice is an
  **implementation-AP decision**; the *design* only fixes the abstraction + injection seam.
- **Test:** the canned response (`nexus.py:76-86`) becomes a **test double** behind the same port —
  removed from the runtime, relocated to tests. This kills "simulated search in prod" (Cap 8).
- **Network policy interaction (cross-track):** real search performs network I/O. Under Track S
  default-secure containment, the sandbox network policy governs egress. Design rule: **search egress
  must be consistent with the active sandbox policy** — if the policy is `network=none`, search either
  runs in the control-plane (host) network *as an explicitly-governed control-plane action* or is
  disabled; this boundary is owned by Track S and documented in `R-05-shared-resolution.md` and
  `S-1-runtime-containment-design.md`. **No hidden network path** (Rule 9).

## 4. File tools & R-05 (shared)

- `read_file`/`write_file` must **stop touching the host FS directly**. They route through the
  containment boundary defined by Track S so that agent file I/O is confined to the approved workspace
  (the repository `cwd` already resolved from `ExecutionRecord.repository`).
- **Ownership:** the *boundary/enforcement* is **Track S** (sandbox); Nexus is the **consumer**. The
  single resolution is in `R-05-shared-resolution.md` — **not duplicated here**.
- **Implementation order:** S provides the confinement seam → H file tools adopt it. (See R-05 doc §order.)

## 5. `execute_command` (keep + inherit)

Already routes through `SandboxManager` with the ADR-010 timeout (`nexus.py:116-125`). It **inherits**
Track S's default-secure containment automatically — no Nexus-side change beyond what Track S changes
in the shared manager. Preserves the single execution chokepoint (Rule 9).

## 6. Error handling & honesty

- Every tool returns a structured `ToolResult`; exceptions become `ok=false` results (not swallowed into
  a fake success).
- The loop's terminal status reflects aggregate tool/decision outcomes (lifecycle-design §2).
- Summarization (`nexus.py:316-336`) stays real; it now summarizes a genuinely real trajectory.

## 7. Architecture preservation

- Ports/injection mirror existing collaborator pattern (`openrouter_client`) — Rule 2, no new framework.
- File/command tools converge on the **sandbox** boundary — Rule 9 (no reach-around), R-05 single-owner.
- No new tools, no new model backends, no governance change — tools remain subject to the existing
  `validate_goal`/governance gate (Rule 5).

## 8. Tier mapping

- **Experimental:** real `SearchProvider` (no canned prod search) + structured tool-calls.
- **Pilot:** file tools confined via R-05 (+ `execute_command` default-secure via Track S).
