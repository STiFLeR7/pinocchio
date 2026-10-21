# ADR-nexus-reality-audit: Nexus Runtime Classified as Prototype

Date: 2026-06-24
Status: Accepted
Release: v1.0.1 "Alignment" · AP-105 · Finding A-005
Related: ADR-nexus-runtime-evaluation, ADR-runtime-v2, ADR-010-execution-timeouts,
`blueprint/implementations/v1.0.1/nexus-reality-audit.md`

---

## Context

Nexus is registered and production-routable as the `"nexus"` agent runtime
(`runners/nexus.py:24`, `orchestrator.py:143,168-216`). The accepted onboarding audit flagged that it
contains simulated behavior. AP-105 was commissioned as an **evidence-based, audit-only** reality check
(no implementation) to establish an accurate capability ledger and a defensible classification, so that
project status (post-A-004) never overstates Nexus.

Key evidence gathered first-hand (full detail in the AP-105 deliverables):

- **Real:** governance-gated goal validation; per-step persistence of `agent_steps`,
  `workflow_checkpoints`, heartbeats, and `execution_artifacts`; real `read_file`/`write_file`/
  `execute_command` tools; real LLM action loop in production config; summarization; clean registry/
  contract integration. Covered by `tests/unit/execution/test_nexus.py`.
- **Simulated / absent:** `web_search` returns canned results unconditionally (`nexus.py:76-86`);
  the plan is a hardcoded, goal-independent literal (`nexus.py:147-151`); `exit_code` is always `0`
  (`nexus.py:284-289`); `terminate()` is a never-invoked no-op (`nexus.py:312-314`); there is no
  resume path (checkpoints are write-only); and `AsyncMock` is imported into the production module with
  a hardcoded decision branch (`nexus.py:7,186-211`).

## Decision

**Classify the Nexus runtime as a Prototype** (degrading to **Concept Demonstration** in the default/
no-API-key configuration, where the decision path is entirely the hardcoded mock branch).

- Nexus **must not** be represented in any project document or status surface as a Production-Ready,
  Pilot-Ready, or Experimental *autonomous research/planning agent*. The authoritative status remains
  **Mocked (partial) / Prototype** in `architecture-status-summary.md`.
- This classification is **evidence-bound**: it changes only when new code + new evidence change the
  ledger — never on the basis of roadmap or intent (`nexus-roadmap-boundary.md`).
- AP-105 authorizes **no implementation, refactor, or fix** to Nexus. The "Required Work" in the
  ledger is descriptive of gaps only.

## Consequences

**Positive**
- Status honesty is preserved (extends A-004): the blueprint cannot drift into over-claiming Nexus.
- A precise, prioritized gap inventory exists (P0: prod test-mock, simulated search, failure-invisible
  exit code) for a *future, separately-authorized* remediation AP.
- The sound parts (governance, persistence, contract, real tool execution) are explicitly recorded so
  they are preserved through any future change.

**Negative / accepted**
- The codebase retains, unchanged, a test-library import and simulation branch in a production module
  until a future code AP addresses it (logged as a gap, deliberately not fixed under AP-105).
- "Multi-runtime execution" remains architecturally real but functionally shallow for the agent path.

**Operational guidance (until remediated)**
- Do not route governed "research"/autonomy tasks to `runtime_id="nexus"` expecting real findings;
  treat any Nexus output as prototype-grade.
- Nexus hardening (file-path confinement, command isolation) is partly gated by **A-006** (sandbox).
