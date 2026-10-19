# Development Guide

> **This file covers Nexus v2** (`nexus_*` packages, the released constitutional platform). Working on
> v1 (`nexus/`) instead? See the root [DEVELOPMENT.md](../../DEVELOPMENT.md).

How to set up, run, and work on Nexus locally. For testing specifics see
[TESTING.md](TESTING.md); for contribution rules see [CONTRIBUTING.md](CONTRIBUTING.md).

---

## 1. Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| Python | 3.12+ | The project targets 3.12 (`requires-python = ">=3.12"`). |
| [uv](https://docs.astral.sh/uv/) | latest | Dependency manager + runner. Installs Python, syncs the locked env, runs tools. |
| Git | any recent | Line endings are normalized to LF via `.gitattributes`. |
| `make` | optional | Convenience task runner. Not required — every target is a thin `uv run` wrapper you can call directly. |

## 2. One-time setup

```bash
git clone https://github.com/STiFLeR7/nexus.git
cd nexus

# Install all dependencies (runtime + dev) from the lockfile, and register hooks.
make install
# equivalently, without make:
#   uv sync
#   uv run pre-commit install
```

That is the entire onboarding. `uv sync` provisions the interpreter and the exact
locked dependency set; `pre-commit install` wires the local quality gate so it
runs automatically on every commit.

## 3. Repository layout (all 32 v2 packages, current for `v2.5.0`)

The six packages below (`nexus_core` through `nexus_harness`) were the original Phase 1–6 foundation and
remain the engineering baseline everything else builds on. The platform has since shipped 26 more packages
across the remaining phases — this table is the full, current inventory, grouped by the four architectural
planes `README.md`'s own "Core Capabilities" table names, not just the earliest layer:

```
# Reasoning & Grounding
nexus_intent/          Intent Resolution — resolves a raw request into a canonical Goal.
nexus_engineering/     Engineering Intelligence — kind-of-work classification, estimation input.
nexus_repository/      Repository Intelligence — repository/codebase grounding.
nexus_history/         Execution History — prior-run grounding for Context/Planning.
nexus_estimation/      Estimation — complexity/cost estimation contract.
nexus_context/         Context Engineering — Goal + inputs -> one immutable Context Package.

# Planning & Governance
nexus_planning/        Planning — Goal -> Plan, Work Packages, Execution Graph, Strategy.
nexus_policy/          Policy Engine — data-driven, fail-closed decision evaluation (ADR-004).
nexus_orchestration/   Orchestration — coordinates a Plan into an Execution Session; never executes.
nexus_harness/         Harness — compiles Harness Requests into runtime-ready Execution Packages.

# Execution
nexus_runtime/         Runtime Manager — allocation, selection, the Harness/Runtime registry (ADR-002).
nexus_runtime_adapters/ Generic runtime adapter registry/discovery layer.
nexus_runtime_llm/    LLM runtime adapter and provider configuration used by the operator CLI.
nexus_runtime_claude/  RuntimeAdapter implementation driving Claude Code.
nexus_runtime_gemini/  RuntimeAdapter implementation driving Gemini CLI.
nexus_runtime_shell/   RuntimeAdapter implementation driving a local shell process.
nexus_execution/       Execution Engine — actuation/dispatch; runs exactly one allocated runtime.

# Post-Execution
nexus_validation/      Validation — judges outcomes from evidence, never a runtime's self-report.
nexus_recovery/        Recovery — classifies failures, decides bounded continuations.
nexus_reflection/      Reflection — post-run reflection reporting.
nexus_knowledge/       Knowledge — durable operational memory.

# Operable-rather-than-just-correct (Scheduler + Approval Exchange + Operations)
nexus_scheduler/       Constitutional Scheduler — governed autonomy, deterministic tick()-driven dispatch;
                       owns the v2 production entrypoint (`python -m nexus_scheduler`).
nexus_approval/        Approval Exchange — the human-in-the-loop gate lifecycle.
nexus_operations/      Operations — read-only observation plane (sessions, health, diagnostics).
nexus_human_interaction/ Human Interaction facade — built, currently unwired to a live entrypoint.

# Substrate and cross-cutting
nexus_core/            Phase 1 foundation — frozen contracts, immutable domain models, validation,
                       registry/event/persistence interfaces, state primitives.
nexus_infra/           Phase 2 infrastructure — concrete event store, event bus, projection engine,
                       snapshot store, repositories, unit of work, and composition (in-memory + durable).
nexus_workflows/       The constitutional reasoning spine driver (`nexus_workflows.spine`) — fuses all
                       nine stages into one `ConstitutionalPipeline`; also the legacy `WorkflowCoordinator`
                       (a disclosed duplicate driver — see `docs/v2/RC1_PRODUCTIZATION_REPORT.md` §7).
nexus_integration/     ADR-008's shadow-migration substrate — built, not yet wired to a live migration.

# Application-layer consumers (built, currently unwired to a production entrypoint)
nexus_operator/        Consumer-application package built on `WorkflowCoordinator`.
nexus_briefings/       Consumer-application package built on `WorkflowCoordinator`.
nexus_research/        Consumer-application package built on `WorkflowCoordinator`.

nexus/                 Legacy v1 application package (separate CI in ci.yml). Zero shared code/schema
                       with any package above.
```

Test directories mirror this 1:1 under `tests/unit/<package-name>/`, plus `tests/integration/` for
cross-package tests (the Scheduler, Approval Exchange, and entrypoint integration suites live there).

```
docs/v2/           Frozen architecture (specs).
adr/               Ratified/proposed Architecture Decision Records.
contracts/         Frozen logical contract specs.
docs/architecture/ The architecture portal — one page indexing every subsystem above.
docs/benchmarks/   Evidence-backed measurements (throughput, replay/restart, test/type coverage).
docs/tutorials/    Guided, progressive learning path (start here if you're new).
examples/          Runnable reference code, one example per architectural capability.
blueprint/v2/      Engineering blueprints / roadmap (v1-era planning artifacts).
```

`nexus_core` is **additive** and never imports from `nexus/`. Its dependency
direction is one-way and acyclic: `contracts → domain → {validation, events,
registries, persistence, state}`. Nothing in it imports a web framework, ORM,
database, or runtime.

## 4. Daily workflow

```bash
make test          # fast inner loop — run the core suite
make check         # full local gate before pushing (lint+format+types+cov)
```

A typical change:

1. Make your edit (respecting the frozen architecture — see CONTRIBUTING.md).
2. `make test` for fast feedback.
3. `make check` to run the complete gate locally.
4. Commit — pre-commit hooks run automatically and may auto-fix formatting.
5. Push and open a PR — Core CI re-runs the same gate.

## 5. Make targets

| Target | What it does |
|--------|--------------|
| `make install` | Sync deps + install pre-commit hooks |
| `make lint` | Ruff lint (no autofix) |
| `make format` | Ruff auto-format in place |
| `make format-check` | Verify formatting (CI mode) |
| `make typecheck` | MyPy strict on `nexus_core` |
| `make test` | Run the core test suite (fast) |
| `make test-cov` | Tests + coverage gate (term/xml/html) |
| `make check` | **Full gate** — lint, format-check, typecheck, test-cov |
| `make pre-commit` | Run all pre-commit hooks against all files |
| `make build` | Build sdist + wheel |
| `make clean` | Remove caches and generated reports |

## 6. Quality gates

The same four checks run locally (`make check`), in pre-commit, and in Core CI — **but not against
identical package scope; know the difference before trusting a local green run:**

| Gate | Command (`make check`'s actual scope, 20 packages) | Rule |
|------|---------|------|
| Lint | `ruff check $(PACKAGES) $(TESTS)` | Configured in `ruff.toml` (single source of truth). |
| Format | `ruff format --check $(PACKAGES) $(TESTS)` | LF line endings, double quotes, 100 cols. |
| Types | `mypy $(PACKAGES)` | `--strict` + `pydantic.mypy` plugin. No `Any` leaks. |
| Tests + coverage | `pytest --cov-fail-under=95` | Branch coverage, ≥95% floor. |

`$(PACKAGES)` in the `Makefile` currently lists 20 of the 32 v2 packages (`nexus_core` through
`nexus_operator`, in dependency order — see §3). **`core-ci.yml` lints and type-checks all 32** — the 12
packages the Makefile doesn't cover (`nexus_policy`, `nexus_intent`, `nexus_engineering`,
`nexus_estimation`, `nexus_repository`, `nexus_integration`, `nexus_history`, `nexus_human_interaction`,
`nexus_approval`, `nexus_operations`, `nexus_scheduler`, `nexus_runtime_llm`) are still gated — just by CI
directly, not by `make check`. This is a real, currently-existing gap between the local dev loop and the
actual CI gate, not a documentation error: `make check` passing is necessary but not sufficient evidence
for those 12 packages.
See §8 for the full command CI actually runs, and `docs/development/CONTRIBUTING.md` §4 for the same
disclosure from the contributor's-eye view.

These checks are otherwise **non-negotiable**: a future change cannot regress architectural correctness or
code quality without failing automated checks, across whichever of the two scopes above actually covers it.

## 7. Tooling configuration map

| Concern | File |
|---------|------|
| Project metadata, deps, pytest, coverage, mypy | `pyproject.toml` |
| Ruff lint + format (authoritative) | `ruff.toml` |
| Pre-commit hooks | `.pre-commit-config.yaml` |
| Core CI pipeline | `.github/workflows/core-ci.yml` |
| Legacy v1 CI | `.github/workflows/ci.yml` |
| Line-ending normalization | `.gitattributes` |
| Task shortcuts | `Makefile` |

> **Ruff note:** Ruff reads `ruff.toml` exclusively when it exists; a
> `[tool.ruff]` block in `pyproject.toml` would be silently ignored, so it is
> intentionally omitted to prevent configuration drift.

## 8. Windows notes

The development shell is bash-compatible (Git Bash / WSL). `make` is optional —
if it is unavailable, run the underlying commands directly. `make check`'s own scope (§6) is:

```bash
uv run ruff check $(cat Makefile | grep '^PACKAGES' | cut -d= -f2) $(cat Makefile | grep '^TESTS' | cut -d= -f2)
uv run mypy $(cat Makefile | grep '^PACKAGES' | cut -d= -f2)
```

(or just read the `Makefile`'s `PACKAGES`/`TESTS` variables directly and paste them — they're plain
space-separated package/directory names.)

**To run the same scope Core CI actually gates (all 32 packages)**, use the exact command
`.github/workflows/core-ci.yml` runs — copy it directly from that file rather than from this document, so
this guide can never drift out of sync with the real gate again the way it once did (§6's own disclosed
gap is exactly this kind of drift, now flagged instead of silently repeated here).

Line endings are LF-canonical; `.gitattributes` + the `mixed-line-ending` hook
keep the working tree consistent across platforms.

## 9. Adding a new package

There is currently **no single source of truth that generates the package list** — three places must be
updated by hand whenever a new `nexus_*` package is added:

1. `pyproject.toml`'s `[tool.hatch.build.targets.wheel] packages` list (so it ships in the wheel).
2. The `Makefile`'s `PACKAGES`/`TESTS` variables, if the new package should be covered by the local
   `make check` loop (see §6 for what's currently included).
3. `.github/workflows/core-ci.yml`'s lint/format/typecheck/test command lines (all four jobs list packages
   explicitly).

This is a known, disclosed gap (not a hidden expectation) — a future improvement could generate all three
from one manifest, but doing so is tooling/CI work, out of scope for a documentation pass. Until then,
verify all three are updated by re-running `make check` **and** confirming the new package appears in a
fresh CI run on your PR, not just locally.

Also add the new package to `DEVELOPMENT.md` §3's layout table (this file) — a package with no entry there
is exactly the kind of undocumented-orphan gap `docs/v2/V1_RELEASE_READINESS_REPORT.md` found and fixed
once already (`nexus_human_interaction`) and would rather not need finding again.

## 10. Adding an ADR

`adr/` holds v2's ratified/proposed Architecture Decision Records — see `adr/README.md` for the full,
canonical index (title, status, date, motivation, impacted subsystems, related ADRs, implementation
references, release introduced — expanded to this shape in
`docs/DOCUMENTATION_PHASE5_REPORT.md`). To propose one:

1. **Do not retrofit an ADR to justify a change already made.** An ADR records a decision *before or as*
   it's implemented, or — for a genuine catch-up case — explicitly and honestly labeled as retrospective.
   `docs/DOCUMENTATION_PHASE5_REPORT.md` §2 investigated a real case where this discipline slipped (two
   decisions referenced as "ADR-005"/"ADR-006" for weeks before anyone noticed neither file had ever been
   written) — don't repeat it.
2. **Follow the existing file header format exactly**: Status, Date, Deciders, Relates (what it depends on
   / what it's distinct from in the other numbering series — see the numbering-collision table in
   `adr/README.md` before picking a number), Affected work/Action Points. `adr/ADR-009-runtime-selection-
   ownership.md` is the most recent real example, including how to file something as **Proposed**, not yet
   ratified, without pretending otherwise.
3. **Number it correctly.** Check `adr/README.md`'s numbering-collision table first — v2's `adr/` series and
   v1's `blueprint/DECISIONS/` series are independently numbered by design; picking the next open v2 number
   (currently `010` is reserved-but-unwritten for the correlation-event gateway) is a real, live constraint,
   not just a formality.
4. **Add it to `adr/README.md`'s index table** in the same PR — a filed ADR that isn't indexed is exactly
   the kind of gap Phase 5 of this repository's documentation initiative exists to prevent from recurring.
5. **Do not edit a ratified ADR's decision to match new code.** If shipped code and a ratified ADR disagree,
   that's a Constitution/implementation conflict — open an issue (§9 of `CONTRIBUTING.md`) or propose a new,
   superseding ADR; never quietly rewrite the old one's Decision section.

## 11. Documentation workflow

When your change affects anything a reader outside your own head needs to know:

- **Code-level docs** (docstrings, package `README.md` if it has one) update in the same commit as the code.
- **Design docs** (`docs/v2/`) are the frozen Constitution — see `CONTRIBUTING.md` §1; you do not edit these
  to reflect an implementation detail. If the design doc and the code have drifted, that's a finding to
  report, not something a code PR silently fixes.
- **Examples** (`examples/`) must stay runnable. If your change alters an API an example calls, update the
  example and re-run it before merging — do not let an example's documented "Expected Output" silently
  become fiction. `docs/DOCUMENTATION_PHASE4_REPORT.md` exists because this exact discipline caught three
  real bugs; skipping it reopens that risk.
- **Benchmarks** (`docs/benchmarks/`) only ever contain a released, re-run measurement with a cited source
  report — see `docs/development/DOCUMENTATION_GUIDE.md`'s benchmark rules before touching this directory.
- For the full house style (writing conventions, Mermaid usage, cross-link expectations, evidence
  requirements) see `docs/development/DOCUMENTATION_GUIDE.md`.

## 12. Release workflow

Release governance (versioning, cadence, the actual commit/tag/merge process, deprecation and support
posture) is documented in full at `docs/releases/README.md` — this section only points you there rather
than duplicating it. In short: there is one `pyproject.toml` version describing the one distributable wheel
(both `nexus` v1 and all 32 `nexus_*` v2 packages ship together); every v2 package's own `__version__`
tracks it; and every past release (`docs/v2/RC1_PRODUCTIZATION_REPORT.md`,
`docs/v2/RC2_EXECUTION_IDENTITY_REPORT.md`, `docs/v2/V1_RELEASE_READINESS_REPORT.md`,
`docs/v2/V2_RELEASE_EXECUTION_REPORT.md`) documents exactly what was done, in what order, with what
verification — read `docs/releases/README.md` before assuming a release step not documented there is
either required or safe to skip.
