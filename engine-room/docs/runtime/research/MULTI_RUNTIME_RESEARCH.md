# Multi-Runtime Research — Implementation

Milestone 3: the same research workflow executes across Claude, Gemini, and Shell by **adapter
substitution alone**, reusing the Runtime Manager's selection unchanged.

## Selection stays the existing funnel

`ResearchCoordinator.select_runtime(policy)` delegates to the existing
`nexus_runtime_adapters.select_runtime`, which reuses the Runtime Manager's own
`RuntimeSelector` (`match → health → policy → choose`). Research adds no selection logic. The
required capability is the abstract `code_generation` every runtime advertises, so:

| Policy | Chosen runtime |
|---|---|
| none | `claude-code` (lowest identity, deterministic tiebreak) |
| `preferred_runtimes=("gemini-cli",)` | `gemini-cli` |
| `candidate_ids=("gemini-cli","shell")` | `gemini-cli` |

Selection depends only on required capabilities, declared capabilities, and policy — never on
heuristics or AI (INV-21).

## Execution across runtimes

`research_across(topic)` runs the identical research request on each runtime and returns one
`ResearchSession` per runtime. Under the hood each run builds a standard pipeline and drives the
existing `WorkflowCoordinator` with a factory that resolves the chosen runtime's adapter — the same
provider-substitution seam Capability Program 2 introduced. Planning, Orchestration, Harness,
Runtime Manager, and Execution are byte-for-byte the same code path.

## What is identical, and what may differ

`test_research_executes_across_every_runtime` asserts all three runtimes succeed, all pass
Validation, and all produce the **same research plan** (identical Work Package ids). The only
differences are the runtime-specific artifacts each provider produces:

| Runtime | Briefing artifact |
|---|---|
| `claude-code` | `wp-…-generate-briefing-main.py` |
| `gemini-cli` | `wp-…-generate-briefing-summary.md` |
| `shell` | `wp-…-generate-briefing-output.txt` |

Governance — validation decisions, recovery decisions — is identical across runtimes
(`test_multi_runtime_briefings_differ_only_in_artifacts`). The research workflow is therefore
genuinely provider-independent: a research brief can be produced on any governed runtime, and the
platform validates and governs it identically.

## Shell "where appropriate"

The shell runtime advertises `code_generation` alongside `command_execution`, so it is eligible for
the same research Work Packages. A research stage on the shell is a command that produces a file —
governed and validated exactly like a model-runtime stage.
