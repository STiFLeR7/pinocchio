# Nexus Documentation Master Plan

**Status: Audit complete. Nothing in this plan has been implemented yet — this document is the
proposal, produced before any documentation file was touched, per this initiative's explicit "audit
first" rule.**

**Scope note:** the repository holds two independent, non-interoperating codebases — v1 (`nexus/`,
released as `v1.0.0`/`v1.0.1`, a Discord-fronted control plane) and v2 (`nexus_*`, 31 packages, just
released as `v2.0.0`, an event-sourced "constitutional reasoning spine"). Nearly every finding below is
really a finding about how the repository presents *two* products through documentation that was mostly
written before the second one existed. That single fact drives most of this plan's recommendations.

---

## 1. Current Documentation Audit

### 1.1 Scale

| Area | Markdown files |
|---|---|
| `docs/v1/` | 15 |
| `docs/v2/` (incl. `actuation/`, `engineering/`, `human_interaction/`, `knowledge/`, `runtime/` subfolders) | 169 |
| `docs/runtime/` | 64 |
| `docs/development/` | 3 |
| `docs/internals/` | 1 |
| `adr/` | 7 |
| `blueprint/` (v1's parallel "living memory" system — `DECISIONS/`, `action-points/`, `architecture/`, `implementations/`, `onboarding/`, `phases/`, `references/`, `reports/`, `v2/`) | 259 |
| Root-level | 8 |

**~526 markdown files total.** No top-level `docs/README.md` or repository-wide index ties `docs/v1/`,
`docs/v2/`, `docs/runtime/`, `docs/development/`, `docs/internals/`, `adr/`, and `blueprint/` together —
a newcomer has no single starting point that explains how these seven trees relate to each other. This is
the largest single navigability gap this audit found.

### 1.2 Root README

`README.md` describes **only v1**: badge line reads `release-v1.0.0 + v1.0.1 alignment`, "Release status"
callout, architecture diagram, capability table, tech stack, quick start, and "Documentation" table are
all v1-specific. It links to `docs/01_ARCHITECTURE.md` (a path that doesn't exist — v1's numbered docs are
actually referenced elsewhere; verify before Phase 2 touches this) and to `blueprint/STATUS.md`. **It does
not mention v2 exists anywhere**, despite v2 now being the tagged, released, actively-developed platform.
This was already flagged as an open decision in `docs/v2/V1_RELEASE_READINESS_REPORT.md` §6 and remains
unresolved. This is the single highest-priority fix in this entire plan — it is the front door, and it is
silent about most of what the repository now contains.

### 1.3 `docs/v2/README.md` is itself stale

The intended index for all of `docs/v2/` still declares:

```
**Status:** Architecture Design (Target)
**Version:** Next Architecture (Pre-v2)
```

and its closing "Design Status" section states the documents "are intentionally independent of the
current implementation." That was accurate when this file was written (Phase 0, pre-implementation) and
is no longer accurate — v2 shipped, was hardened twice (RC1, RC2), and is tagged `v2.0.0`. This file needs
a status update more urgently than almost anything else in `docs/v2/`, because it's the entry point every
other v2 doc link points back to.

### 1.4 Duplicate-named, disjoint-content file pairs

| Root file | `docs/development/` equivalent | Finding |
|---|---|---|
| `CONTRIBUTING.md` | `CONTRIBUTING.md` | Same filename, **completely different content** — root is v1's contribution guide (blueprint/AP process, Discord-era workflow); `docs/development/` is v2's (frozen-architecture rules, `make check` gate). Neither is wrong; the naming collision is the problem. |
| `DEVELOPMENT.md` | `DEVELOPMENT.md` | Same pattern — root is v1 (pip/venv/Discord config), `docs/development/` is v2 (`uv`/`make`, current and well-maintained). |

Anyone landing on `CONTRIBUTING.md` at the repo root today has a 50/50 chance of reading instructions for
the wrong codebase, with no signal at the top of either file to redirect them.

### 1.5 Root-level files that read as one-off artifacts, not durable docs

| File | Finding |
|---|---|
| `mcp_report.md` | Two lines, no real content ("MCP adoption grows"). No connection to Nexus's own architecture. Reads as an accidental scratch file. |
| `NEXUS_DOCUMENTATION_ALIGNMENT_SUMMARY.md` | A commit-pinned, dated executive summary of a single past audit pass (AP-104, v1.0.1). Predates v2 entirely. Its natural home is `blueprint/implementations/v1.0.1/`, where its source artifacts already live. |
| `NEXUS_FIRST_IMPRESSION.md` | A commit-pinned onboarding-auditor report on v1.0.0 specifically (maturity score, named commit `aa3e527`). Same shape as above — a snapshot report that leaked to root instead of living under `blueprint/onboarding/`. |
| `ONBOARDING.md` | Actively misleading, not just stale: it states the project is "currently in pre-Phase 0" and lists Phase 0 tasks as "first available work," which directly contradicts a repository that has shipped v1.0.0, v1.0.1, and now v2.0.0. |

None of these were invented for this audit to complain about — they're genuine, currently-reachable files
a new contributor can click into from GitHub's file browser today.

### 1.6 `docs/runtime/` — investigated, and it is *not* a duplicate

Given how closely `docs/runtime/{knowledge,recovery,validation,reflection,research,workflows,...}/` mirror
`docs/v2/`'s subsystem folder names, this looked like a stale pre-restructure draft. It isn't. Git history
shows `docs/v2/` was written first (Phase 0 design), and each `docs/runtime/<subsystem>/` folder landed
*with* that subsystem's implementation, weeks later — e.g. `docs/runtime/recovery/RECOVERY_ENGINE.md`
opens by stating it "conforms to the frozen architecture in `docs/v2/19_RECOVERY.md`... these are
engineering documents, not architecture." Real package code cites it directly:
`nexus_recovery/vocabulary.py` and `nexus_validation/vocabulary.py` reference
`docs/runtime/recovery/RECOVERY_DECISIONS.md` and `docs/runtime/validation/VALIDATION_RULES.md` by path.
**This is live, cited, as-built engineering documentation — not historical cruft.** Its one real gap: no
top-level `docs/runtime/README.md` explains the tree's purpose or its relationship to `docs/v2/` (only
`docs/runtime/assessment/README.md`, for one specific subfolder, exists). `docs/v1/` is confirmed
unrelated to either — a self-contained early v1 design brief with no naming overlap.

### 1.7 ADR gaps and the ratification report's blind spot

7 ADR files exist (`ADR-001` through `004`, then `007`–`009`); **no `ADR-005` or `ADR-006` file exists**,
yet both are referenced roughly 20 times across `docs/v2/` (`ARCHITECTURE_CONSTITUTION.md`,
`CONSTITUTIONAL_MIGRATION_BLUEPRINT.md`) as "Accepted in P0" decisions (reinstating Engineering
Intelligence; naming Policy/Repository-Intelligence/Actuation/Operations as first-class subsystems).
`docs/v2/ADR_RATIFICATION_REPORT.md` — the file whose entire job is tracking ADR status — never mentions
this gap. (A *separate*, legacy `blueprint/DECISIONS/ADR-005-agent-routing.md` /
`ADR-006-approved-tech-stack.md` pair exists for v1, on an intentionally different numbering track,
already disambiguated by a note in ADR-007/008 — that collision is understood and documented; the v2-side
005/006 gap is not.) ADR-009 itself is correctly and consistently marked **Proposed, unratified**
everywhere it's cited — that part of the ADR system is working as designed.

### 1.8 Package README coverage is inconsistent, but not accidental

Only 6 of 31 v2 packages have their own `README.md`: `nexus_core`, `nexus_infra`, `nexus_planning`,
`nexus_context`, `nexus_orchestration`, `nexus_runtime`. These are exactly the earliest, most
foundational build phases (Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 → Phase 8A) — each README adds
real value beyond its package's `__init__.py` docstring (module-layout tables, runnable cross-package
usage examples, verification commands), and all 6 are current. The other 25 packages have no README at
all — the practice appears to have lapsed under time pressure as the program moved toward the v2.0.0
release, not from a deliberate scoping decision.

### 1.9 Terminology drift — three names for one platform

| Where | Tagline |
|---|---|
| Root `README.md` | "AI Orchestration Control Plane" |
| `docs/v2/README.md` | "Operational Intelligence Platform" |
| RC1/RC2/Release reports, `CHANGELOG.md`'s own `[2.0.0]` entry, `ARCHITECTURE_CONSTITUTION.md` | "constitutional reasoning spine" / "constitutional [platform/spine]" |

All three are describing the same v2 system at different points in its own program history (vision doc →
mid-build → shipped). None is factually wrong, but a reader crossing between them has no signal these are
the same thing, and no doc explains the lineage.

### 1.10 What's missing outright

- No `examples/` directory exists at all.
- No `CODE_OF_CONDUCT.md` or `SECURITY.md`.
- No diagrams as image assets and no Mermaid diagrams anywhere in `docs/` or `README.md` — all existing
  "diagrams" are ASCII art in code fences (this is consistent, at least, and not necessarily wrong for a
  text-first repo — see §3).
- Root `README.md` line 110 links to `docs/01_ARCHITECTURE.md` — **verified broken**; no such file exists
  (v1's numbered docs live at `docs/v1/01_ARCHITECTURE.md`). A concrete, fixable dead link Phase 2 should
  correct, not just an audit observation.
- `docs/v2/README.md`'s "Document Structure" table promises a `contracts/` directory — **verified this
  exists** (`contracts/artifact.md`, `capability.md`, `checkpoint.md`, `context_package.md`, etc.) and is
  correctly referenced. Not a gap.

### 1.11 What's already good and should be preserved, not redone

- `docs/development/{CONTRIBUTING,DEVELOPMENT,TESTING}.md` (v2's trio) are accurate, current, well
  cross-linked, and match the actual `Makefile`/`core-ci.yml`/`ruff.toml` setup exactly. This is the model
  to extend to the rest of the DX work, not replace.
- The `Makefile`'s `check` target (`lint format-check typecheck test-cov`) already matches CI exactly —
  a new contributor has one command that reproduces the CI gate locally.
- `CHANGELOG.md` follows Keep a Changelog format correctly and has a real, honest `[2.0.0]` entry already.
- The numbered `docs/v2/00`–`26` design docs plus `docs/runtime/`'s as-built engineering docs together
  already form a genuinely rare thing: a large system where design intent and implementation reality are
  both documented and (per this session's own release audit) verified consistent with the shipped code.
  The gap is entirely in *navigation and currency signaling*, not in missing engineering rigor.

---

## 2. Documentation Information Architecture

**Principle: reduce navigation cost, not content.** Nothing audited above needs to be deleted for being
wrong — most of it needs to be found, dated, and connected. The existing `docs/v1/` `docs/v2/`
`docs/runtime/` `docs/development/` `docs/internals/` split is already a reasonable shape; it just has no
index and two root-level naming collisions.

Proposed top-level shape (minimal moves, maximum clarity):

```
docs/
    README.md                  # NEW — the one page that explains all trees below and how they relate
    getting-started/           # NEW — the reader's actual first stop (Phase 2/8 material lives here)
    architecture/              # NEW alias/index over existing docs/v2 design docs (see §4) — no file moves
    adr/                       # NEW index page only; adr/ directory itself stays at repo root (tooling/link stability)
    concepts/                  # NEW — short, single-topic explainers extracted from docs/v2 for newcomers
    guides/                    # NEW — task-oriented how-tos (write a policy, add a runtime adapter, etc.)
    operators/                 # RENAME target for docs/v2/OPERATOR_GUIDE.md (or leave in place + index link — see below)
    examples/                  # NEW, see §7 — top-level, not under docs/, so it's runnable/discoverable via GitHub's file tree
    tutorials/                 # NEW, see §8
    benchmarks/                # NEW, see §6
    releases/                  # NEW index over CHANGELOG.md + docs/v2/*_REPORT.md release history
    internals/                 # EXISTING (docs/internals/WALKTHROUGH-v2.md) — this is the right home for code-level tours; add more here over time
    v2/                        # EXISTING — kept as-is (169 files, actively cited, do not restructure wholesale)
    runtime/                   # EXISTING — kept as-is (cited from code); add the missing docs/runtime/README.md (§1.6)
    v1/                        # EXISTING — kept as-is, clearly historical/separate
    development/               # EXISTING trio — keep, it's the best-maintained corner of the repo
```

**Explicit recommendation: do not move or renumber the 169 files under `docs/v2/` or the 64 under
`docs/runtime/`.** Both are cited by path from other docs and from package docstrings/vocabulary modules
(§1.6). Moving them breaks live references for zero navigability gain — the fix is an index layer on top
(`docs/README.md`, `docs/architecture/README.md` as a curated table of contents into the existing files),
not a file-system reshuffle. This directly follows the rule "reduce cognitive load... improve
discoverability" without the rule "flatten nesting" implying a rewrite of a system that already works.

**Naming-collision fix:** rename the two root-level v1 docs to make their scope explicit at a glance —
`CONTRIBUTING.md` → `CONTRIBUTING-v1.md`, `DEVELOPMENT.md` → `DEVELOPMENT-v1.md` (or move both under a new
`docs/development-v1/` to mirror `docs/development/`'s existing v2 location) — and add one line at the top
of whichever file remains at the canonical root path, pointing to the other. This is the single cheapest
fix in this whole plan for the single most-confusing finding in §1.4.

---

## 3. README Strategy

The redesigned root `README.md` must do one new thing today's doesn't: **honestly represent that this
repository contains two products**, without pretending v1 doesn't exist or burying v2 as a footnote.
Recommended structure (mapping the governing prompt's 16-point list onto what the audit actually found):

1. **What is Nexus?** — one sentence per generation. v1: an AI orchestration control plane for
   Discord-governed execution, released and pilot-operating. v2: an event-sourced constitutional
   reasoning spine, released as `v2.0.0`, independent of v1 (zero shared code, schema, or process).
2. **Why does it exist? / What problems does it solve?** — draw from `docs/v2/00_VISION.md`'s actual
   framing ("execution is commoditizing; operational intelligence is the differentiator") rather than
   re-marketing v1's already-good "de-fragments AI operations" framing — state both, since they answer
   different questions (v1: operational fragmentation; v2: reasoning-before-execution).
3. **Why is it different?** — determinism, event-sourcing, single-owner-per-decision governance
   (INV-02), replay/restart as first-class guarantees, not retrofits. This is genuinely differentiated
   and already true today — state it as fact, not aspiration (per the "no exaggeration" rule).
4. **Core architecture** — one diagram, v2 only (v1's existing ASCII diagram can stay under a v1 section).
5. **Major capabilities** — the 13-capability model table, sourced from `ARCHITECTURE_CONSTITUTION.md`,
   not reinvented.
6. **Quick architecture diagram** — see §4 for the Mermaid proposal.
7. **Installation / Quick Start** — two blocks, clearly labeled v1 vs v2 (`pip install -e ".[dev]"` +
   `python -m nexus` vs `uv sync` + `python -m nexus_scheduler`), since they use different package
   managers and entrypoints today — collapsing them into one would misrepresent the repo.
8. **Example workflow** — one v2 example, linked to §7's example library once it exists.
9. **Documentation map** — link to the new `docs/README.md` index (§2), not a flat file list.
10. **Integrations** — the runtime adapters (`nexus_runtime_claude`/`gemini`/`shell`) and v1's Discord/
    Email adapters, listed honestly by maturity (matching the existing v1 status table's ✅/🟡/🟠
    discipline — that convention is good and should carry over to v2's section).
11. **Screenshots/diagrams** — none exist today (§1.10); placeholder callout only, explicitly marked
    "planned," never a fabricated image.
12. **Roadmap** — link `blueprint/ROADMAP.md` (v1) and a to-be-created v2 roadmap pointer (§11).
13. **Community** — needs `CODE_OF_CONDUCT.md`/`SECURITY.md` to exist first (§1.10) before this section
    can be more than a placeholder.
14. **License** — already correct (MIT, `LICENSE` added in the v2.0.0 release).

**Tone:** match the existing root README's own register (`Determinism over cleverness`, tight
principle-statements, ✅/🟡/🟠 status markers) — it's already engineering-focused, not marketing-heavy.
Extend that voice to v2 rather than introducing a new one.

---

## 4. Architecture Documentation Plan

**Do not rewrite `ARCHITECTURE_CONSTITUTION.md`, the numbered `docs/v2/00`–`26` docs, or
`99_ARCHITECTURAL_INVARIANTS.md`.** This session's own prior release audit already verified these against
the shipped implementation and found them consistent (with one known, deliberately-undisclosed exception:
ADR-009's pending INV-37 correction — already tracked as an open risk, not new work for this initiative).

What's actually needed is the **index and currency-signaling layer** identified in §1.3:

1. Fix `docs/v2/README.md`'s status header — replace "Architecture Design (Target)" / "Pre-v2" with the
   real state ("Implemented and released — `v2.0.0`") and update its "Design Status" closing section,
   which currently disclaims any connection to the actual implementation.
2. Produce **one architecture index** (`docs/architecture/README.md` or extend `docs/v2/README.md`
   in place) covering exactly the list the governing prompt names: system overview, subsystem
   responsibilities, execution lifecycle, replay, scheduler, governance, memory, operations, runtime,
   approval, orchestration — as a curated table of pointers into the *existing* docs (§2's principle:
   index, don't move), cross-referencing `docs/internals/WALKTHROUGH-v2.md` for the code-level version of
   the same tour.
3. Add Mermaid diagrams **only where they clarify something the existing ASCII art doesn't** — the
   09-stage Spine pipeline (§5 of `WALKTHROUGH-v2.md`) and the four-plane package map are the two
   strongest candidates; this repository's existing convention of ASCII-in-code-fences is legible and
   git-diffable, so Mermaid should supplement it for the architecture index specifically, not replace it
   repository-wide.
4. Add the `docs/runtime/README.md` index identified in §1.6, stating explicitly: "these are per-package,
   as-built engineering records, subordinate to the frozen design in `docs/v2/` — not a duplicate of it."

---

## 5. ADR Improvements

1. **Resolve or disclose the ADR-005/006 gap (§1.7).** Two options, in order of preference: (a) if the
   "Accepted in P0" decisions `ARCHITECTURE_CONSTITUTION.md` attributes to ADR-005/006 are real,
   already-made decisions that were simply never written up as standalone files, write them now as
   `adr/ADR-005-*.md` / `adr/ADR-006-*.md` with Status: Accepted, dated to when the decision actually
   entered the Constitution — this is documentation catch-up, not inventing a new decision, and is
   explicitly allowed ("flag any missing ADRs, but do not invent decisions" — the decisions already exist
   in prose; this formalizes them). (b) If on closer reading any of those references turn out to be
   aspirational rather than settled, `ADR_RATIFICATION_REPORT.md` must say so explicitly instead of
   staying silent. Either way, **do not leave the ratification report silent on a gap it exists to catch.**
2. **Add the 005/006 disambiguation note** (mirroring the existing ADR-007/008 v1-numbering-collision
   note) directly into `ADR_RATIFICATION_REPORT.md`.
3. **Produce one ADR index page** (`docs/adr/README.md` or extend `ADR_RATIFICATION_REPORT.md`) listing,
   per ADR: number, title, status, date, one-line decision, and every file that implements or is
   constrained by it — the table in §1.7 of this plan is a ready-made first draft.
4. **No new ADRs should be authored speculatively.** ADR-010 (the correlation-event gateway / INV-39
   transport freeze, per `ADR_RATIFICATION_REPORT.md`'s own existing note) stays a documented gap, not
   something this documentation initiative writes.

---

## 6. Benchmark Documentation

Real, measured evidence already exists and has never been surfaced outside internal release reports.
**Only this data — nothing fabricated** — populates the new `benchmarks/` section:

| Metric | Source | Measured value |
|---|---|---|
| Scheduler `tick()`, 10 schedules | `RC1_PRODUCTIZATION_REPORT.md` §6.1 | 0.09 ms (was 0.5 ms pre-fix) |
| Scheduler `tick()`, 500 schedules | same | 3.29 ms (was 1136.6 ms — ~345x) |
| Scheduler `tick()`, 2000 schedules | same | 14.4 ms |
| Event throughput, in-memory (2000 events/1 txn) | same §6.2 | 145,072 events/sec |
| Event throughput, durable (2000 events/1 txn) | same | 17,389 events/sec |
| Replay throughput (2200 events) | same | 170,989 events/sec |
| Replay at scale (20,000 events) | same | 92,742 events/sec, 215.7 ms |
| Restart latency (2200 events) | same | 15.35 ms |
| Restart at scale (20,000 events) | same | 180.9 ms |
| Full test suite | `V2_RELEASE_EXECUTION_REPORT.md` §4 | 3215 passed, 1 skipped (opt-in), 0 failed |
| mypy --strict coverage | same | 388 source files, 0 errors |
| CI (5 required/tracked jobs) | same | all green on the `v2.0.0` merge commit |

**Explicitly out of scope for this pass:** any number not already measured and recorded in an existing
release report. The benchmarks page should state its own methodology caveat verbatim from
`RC1_PRODUCTIZATION_REPORT.md` §6 — "single-machine, single-run, order-of-magnitude and shape, not
calibrated production SLAs" — rather than presenting these as production SLAs. Future benchmark
categories the prompt names but no measurement exists for yet (validation overhead as a standalone
number, coverage percentage as a tracked trend over time) should appear as **explicitly labeled
placeholders** ("not yet measured — tracked for a future pass"), never invented.

---

## 7. Example Library

No `examples/` directory exists today — this is a real build, not a reorganization, and per the prompt's
own instruction ("prefer quality over quantity"), it should ship as a small number of genuinely runnable,
documented examples rather than nine thin stubs. Proposed set, each backed by an API that already exists
and is already tested (no new platform capability, per this initiative's own constraint):

| Example | Demonstrates | Backing API |
|---|---|---|
| `01_minimal_pipeline` | The smallest possible Goal→Knowledge run | `ConstitutionalPipeline.run(SpineRequest(...))` — `nexus_workflows/spine/coordinator.py` |
| `02_autonomous_workflow` | A goal dispatched under `FULLY_AUTOMATIC` autonomy | `nexus_scheduler.schedule_goal` + `Scheduler.tick` |
| `03_approval_workflow` | A gated node pausing for, then resuming after, approval | `nexus_approval.ApprovalExchange` |
| `04_scheduled_execution` | A recurring schedule dispatching independent occurrences | `Scheduler.schedule_goal` with an interval trigger (the exact scenario RC2's regression test covers) |
| `05_replay_and_restart` | Reconstructing a session from the durable log after a process restart | `bootstrap()` called twice over one `--db` file, per `tests/integration/test_v2_entrypoint.py` |
| `06_policy_enforcement` | A `DecisionRequest` denied by a custom policy (fail-closed default) | `nexus_policy.PolicyEngine` |
| `07_runtime_adapter` | Writing a minimal custom `RuntimeAdapter` | `nexus_execution.adapter.RuntimeAdapter` protocol, using `nexus_runtime_shell` as the reference implementation |

Every example must actually run against the released `v2.0.0` package (verified by a smoke test in CI, not
just prose) and link to the relevant `docs/v2/NN_*.md` design doc and `docs/internals/WALKTHROUGH-v2.md`
section. Memory/knowledge usage was in the prompt's list but is better served by extending example 01
(a knowledge-producing goal) than a standalone example, to keep the library small per "quality over
quantity."

---

## 8. Tutorial Roadmap

Ordered so each tutorial only depends on concepts the previous one already introduced:

1. **First Pipeline** — install, `python -m nexus_scheduler --once`, submit one Goal, read the resulting
   events back. (Builds on Example 01.)
2. **Scheduler Basics** — one-time vs. recurring schedules, what `tick()` actually does, why nothing
   fires on a wall clock without it. (Builds on 1; uses Example 04.)
3. **Governance & Policy** — how a `DecisionRequest` is evaluated, why the default is fail-closed, writing
   your first policy rule. (Builds on 2; uses Example 06.)
4. **First Autonomous Workflow** — Manual → Governed → Fully-Automatic, and what changes at each level.
   (Builds on 3.)
5. **Approvals** — pausing at a gated node and resuming after a human decision. (Builds on 4; uses
   Example 03.)
6. **Replay & Recovery** — restarting a process against the same durable log; what Recovery does after a
   failed execution. (Builds on 1–5; uses Example 05.)
7. **Memory / Knowledge Basics** — how a completed execution becomes a durable Knowledge item, and how a
   later Goal consumes it.
8. **Building a Runtime Adapter** — the last and most advanced tutorial, since it requires understanding
   everything above it. (Builds on all prior; uses Example 07.)

This order deliberately differs slightly from the prompt's own listed order (Memory Basics moved after
Recovery, Governance moved earlier) because Memory/Knowledge is the terminal stage of the pipeline
(§5 of `WALKTHROUGH-v2.md`) and can't be meaningfully demonstrated before Recovery/Validation exist in the
reader's mental model, while Governance/Policy is load-bearing from the very first pipeline run (every
stage consults it) and benefits from being introduced early.

---

## 9. Release Documentation

Most of the raw material already exists from this session's own release execution; it needs to become a
standing, repeatable process document rather than living only in one-off reports:

- **Versioning strategy:** already established this release — semantic versioning, v2 and v1 share one
  `pyproject.toml` version field describing the one distributable wheel; document this explicitly
  (it's a real, slightly unusual constraint a new release engineer would otherwise have to rediscover from
  `V1_RELEASE_READINESS_REPORT.md` §3's own note about it).
- **Release checklist:** `V1_RELEASE_READINESS_REPORT.md` §8 and `V2_RELEASE_EXECUTION_REPORT.md` already
  contain a real, exercised checklist (version consistency, LICENSE, mypy/ruff/tests, wheel build, commit
  plan, tag verification) — promote this into a standing `releases/CHECKLIST.md` rather than leaving it
  buried in a point-in-time report.
- **Changelog process:** already Keep-a-Changelog format and already has a documented past failure mode
  worth learning from — `CHANGELOG.md`'s own header notes it once omitted the v1.0.0 release entirely and
  had to be forensically reconstructed (AP-104). State the lesson explicitly in the new process doc: the
  changelog entry is part of the release checklist, not an afterthought.
- **Migration guidance:** `docs/v2/RC1_MIGRATION_GUIDE.md` already exists and is current; link it, don't
  duplicate it.
- **Deprecation/support policy:** does not exist today for either v1 or v2 — genuinely new, and should
  stay minimal (e.g., "v1 and v2 are independent; deprecating one has no effect on the other's support
  window") rather than inventing a policy neither codebase has actually committed to yet.

---

## 10. Developer Experience Improvements

Target: a new contributor productive in under 30 minutes. Current state is closer to this than the rest
of the audit might suggest — `docs/development/`'s trio plus the `Makefile`'s `make check` gate are
already good. The gap is entirely in **findability**, not in the underlying content:

1. Fix the root `CONTRIBUTING.md`/`DEVELOPMENT.md` naming collision (§2) — this is the single highest-
   leverage DX fix available, because it's the first file most tooling (GitHub's "Contributing" prompt,
   `git clone` README-adjacent browsing) surfaces to a new contributor.
2. Rewrite or retire `ONBOARDING.md` (§1.5) — its "pre-Phase 0" framing actively misleads a new
   contributor about the project's actual maturity today.
3. Relocate `NEXUS_DOCUMENTATION_ALIGNMENT_SUMMARY.md` and `NEXUS_FIRST_IMPRESSION.md` into
   `blueprint/implementations/v1.0.1/` and `blueprint/onboarding/` respectively, where their source
   artifacts already live; delete `mcp_report.md` outright (two content-free lines, no connection to this
   project — flagged for confirmation before deletion, not deleted unilaterally by this plan).
4. Add a `docs/README.md` index (§2) as the single "start here" link every other entry point (root
   README, both CONTRIBUTING files, `docs/v2/README.md`) should point to.
5. Extend the existing package-README pattern (§1.8) to at least the packages a new contributor is most
   likely to touch first (per the tutorial roadmap's own ordering: `nexus_scheduler`, `nexus_policy`,
   `nexus_workflows/spine`) rather than all 25 remaining packages at once.

---

## 11. Prioritized Implementation Plan

Ordered by leverage (impact ÷ effort), not by the phase numbering in the governing prompt:

| Priority | Item | Why first |
|---|---|---|
| 1 | Fix `docs/v2/README.md`'s stale "Pre-v2/Target Architecture" status header (§1.3, §4.1) | One file, highest-visibility factual error in the whole audit — the index for 169 files currently denies its own subject was ever built |
| 2 | Rename root `CONTRIBUTING.md`/`DEVELOPMENT.md` → `-v1` and add cross-pointers (§1.4, §2, §10.1) | Cheapest fix, resolves the most-cited confusion risk |
| 3 | Redesign root `README.md` to acknowledge v2 (§3) — the open decision from the last release's report | Highest-visibility gap; blocks everything downstream that wants to link "the README" as an entry point |
| 4 | Add `docs/README.md` top-level index (§2) | Makes every other fix in this list actually reachable |
| 5 | Relocate/retire the four stray root files (§1.5, §10.3) | Low effort, removes actively misleading content (`ONBOARDING.md`) |
| 6 | Resolve or disclose the ADR-005/006 gap (§1.7, §5) | A ratification report that's silent on a real gap undermines trust in the rest of the ADR system |
| 7 | Add `docs/runtime/README.md` index (§1.6, §4.4) | Small, removes the last real navigability gap in an otherwise-sound tree |
| 8 | Publish the benchmarks page from already-measured data (§6) | Pure exposition of existing evidence, no new measurement work |
| 9 | Build the example library (§7) | Highest-effort item; sequence after the doc-navigation fixes above so examples land somewhere discoverable |
| 10 | Write the tutorial series (§8) | Depends on the example library existing first |
| 11 | Formalize the release-process docs (§9) | Lower urgency — the underlying process already works, this just durably records it |
| 12 | Extend package READMEs to the next tier of packages (§10.5) | Ongoing, incremental, never really "done" |

**Everything above is a proposal.** Per this initiative's own first rule, no file has been modified to
produce this plan. The next step is confirming this prioritization (or reordering it) before any
implementation phase begins.
