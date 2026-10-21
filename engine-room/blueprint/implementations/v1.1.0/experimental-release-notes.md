# Nexus Experimental — Release Notes (v1.1.0 "Containment", H-2)

> Audience-facing notes for the Track H / H-2 increment. H-2 is the second completed track of v1.1.0
> (after Track S); the v1.1.0 release itself remains open pending Pilot (H-4). Documentation only.

---

## Headline

**Nexus is now honest.** Its production path no longer simulates intelligence — it makes real model
decisions via structured tool-calls, searches through an injectable provider, plans from the goal, and
reports truthful success/failure. Maturity: **Prototype → Experimental**.

## Highlights

- **No production mock.** The `AsyncMock` import and `is_mocked` branch are gone; a missing key no longer
  silently downgrades to canned behavior. Guard-tested.
- **Provider-backed search.** `web_search` runs through an injected `SearchProvider` (DI). The canned MCP
  text is removed from the runtime; with no provider configured, search returns an honest error rather
  than fake results.
- **Goal-derived planning.** Plans are generated from the goal (model or goal-derived fallback); the
  decorative hardcoded plan is removed.
- **Structured tool-calls.** Model output is parsed as a schema-validated tool-call; a malformed call is
  an explicit failure, never a silent "finish".
- **Truthful outcomes.** `execute_goal` returns an outcome-derived `exit_code`/`status`; failed steps
  persist `FAILED`; the orchestrator finalizes real failures as FAILURE.

## Classification

| | |
|---|---|
| Before | 🔴 Mocked / **Prototype** |
| After | 🟠 **Experimental** (`ADR-hermes-experimental`) |
| Simulated-in-prod capabilities | 5 → **0** |

## Operator guidance

- **Experimental use:** Nexus can be exercised as an honest agent runtime; outcomes (success/failure)
  are now trustworthy and audited.
- **Search:** inject a real `SearchProvider` for live search; bind its egress to the sandbox network
  policy. Without one, `web_search` returns an explicit "no provider configured" error (safe default).
- **Not yet lifecycle-safe:** there is **no** cancellation and **no** resume. An interrupted run cannot
  be stopped mid-flight and restarts from zero — do not run Nexus unattended for long tasks. That is the
  Pilot bar (H-4).

## Known limitations (Pilot bar / H-4)

`terminate()`/cancellation, `resume_goal()`, fail-fast init, configurable budget, `TIMED_OUT` lifecycle,
and one audited real governed run remain. In-container file I/O ceiling (R-05) is P2 (the host-side
workspace floor is already enforced by Track S / S-4).

## Compatibility / impact

- **No behavior change** to CLI runtimes (Gemini/Claude), scheduler, governance, memory, events, schema,
  or migrations. No new tools, agents, or model backends.
- `AgentRuntimeAdapter` contract, RuntimeRegistry, orchestrator, and the Track-S sandbox seam preserved.
- Full suite **194 passed** (178 → 194, +16); ruff + mypy clean; zero regressions.

## Verification

| Gate | Result |
|---|---|
| Tests | 194 passed (project venv) |
| Lint | ruff — all checks passed |
| Types | mypy — no issues, 60 files |

## Status

H-2 is **complete and frozen for commit**; the maturity upgrade is effective on commit to
`v1.1.0-planning`. Track H continues with H-4 (Pilot). v1.1.0 release tagging waits until Pilot.
