# Documentation Phase 7 Report — Developer Experience, Tutorials & Project Governance

**Status: Complete. No implementation, tooling, or architecture change was made.** This phase touched only
Markdown documentation: new tutorials and getting-started content, targeted edits to the three
`docs/development/` files and the three root v1 files, two new governance documents, and small polish fixes
to headings and code-fence tags. `git status --short` (see §6) confirms zero `nexus_*`, `tests/`,
`scripts/`, `pyproject.toml`, `Makefile`, `ruff.toml`, or `.github/` files were touched.

This is the seventh and final phase of the Nexus Documentation & Developer Experience Initiative. This
report closes it.

---

## 1. Tutorials Added

`docs/tutorials/` — ten tutorials plus an index, exactly the progression the governing prompt suggested:

| # | Tutorial | Builds on | Example referenced |
|---|---|---|---|
| 01 | Installing Nexus | — | `examples/01-hello-nexus/` (verification step) |
| 02 | Running Your First Pipeline | 01 | `examples/01-hello-nexus/` |
| 03 | Understanding the Constitutional Pipeline | 02 | `examples/02-first-pipeline/` |
| 04 | Working with Memory | 03 | `examples/05-memory/` |
| 05 | Scheduling Work | 03 | `examples/06-scheduler/` |
| 06 | Approval Exchange | 03 | `examples/07-approval-exchange/` |
| 07 | Replay & Recovery | 05 | `examples/08-replay/`, `examples/09-recovery/` |
| 08 | Runtime Adapters | 03 | `examples/04-runtime-selection/` |
| 09 | Policy Authoring | 03 | `examples/03-policy-governance/` |
| 10 | Building Your First Autonomous Workflow | 04–09 | `examples/10-autonomous-workflow/` |

**No tutorial duplicates an example's code.** Each one names the exact `examples/NN-*/run.py` file and its
README, explains the *concept* (why the mechanism works the way it does, what it composes with), gives a
"Check your understanding" pair of questions with answers, and a "Go deeper" pointer into the design
reference (`docs/v2/`, `docs/architecture/README.md`, ADRs, or `docs/benchmarks/`) — never re-pasting the
example's source. This was a deliberate choice to keep the tutorial series maintainable: if an example's
code changes, only its own README needs updating, not ten tutorial files that quoted it.

The learning path in `docs/tutorials/README.md` explains the ordering rationale: 01–03 are linear and
mandatory: everything after 03 branches independently from the same base (04–09 can be read in any order,
each depending only on 03), and 10 is the capstone composing all of them, mirroring
`examples/10-autonomous-workflow/`'s own role as the example library's showcase.

---

## 2. Getting Started Experience

`docs/getting-started/README.md` — the explicit "clone → install → run first example → understand
architecture → continue into tutorials" journey the governing prompt specified, with a stated target of a
first successful run in under 15 minutes.

**Verified against actual timing, not assumed:** `uv sync` (1–2 minutes) plus running
`examples/01-hello-nexus/run.py` (seconds, already confirmed to run cleanly in Phase 4's own validation
pass) plus reading the root README's "What is Nexus?"/"Core Capabilities"/"Architecture" sections (roughly
5 minutes) comes to well under 15 minutes total — the target is achievable with the actual commands listed,
not an optimistic guess.

A "What 'success' looks like at each step" table gives a concrete, checkable signal for every stage (clone,
install, first example, architecture, tutorials), and the Troubleshooting section reuses the exact,
already-verified failure modes from `examples/README.md` (`ModuleNotFoundError`, `UnicodeEncodeError`)
rather than inventing new ones.

---

## 3. Contributor Documentation

Reviewed `CONTRIBUTING.md` (root, v1) and `docs/development/CONTRIBUTING.md` (v2) per the governing
prompt's instruction; found `docs/development/CONTRIBUTING.md` genuinely stale relative to the released
`v2.0.0` platform and fixed it in place (not rewritten wholesale — most of it was already accurate and is
explicitly called out in the master plan as "the model to extend," so this phase extended it rather than
replaced it):

- **A real branch-naming bug, fixed.** §2 previously told v2 contributors to "branch from the active
  planning branch (e.g. `v1.2.0-planning`)" — that branch is **v1's** planning branch, unrelated to v2.
  Corrected to branch from `master`, with an explicit note about the naming collision so it doesn't recur.
- **A real, disclosed gap between `make check` and CI, not previously stated anywhere.** The `Makefile`'s
  `PACKAGES` variable covers 20 of the 31 shipped v2 packages; `core-ci.yml` lints and type-checks all 31.
  Verified directly against both files (not assumed) before writing this down. §4 and §5 now state this
  plainly, and the "Definition of done" checklist was updated to require the broader CI check for anyone
  touching one of the 11 uncovered packages.
- **A stale "Phase 1 foundation, later phases not yet built" scope boundary, removed.** The old §6 named
  event bus, persistence backends, orchestration, planning, runtime, and APIs as "later phases" not to
  implement against the foundation — every one of these shipped in `v2.0.0`. Replaced with a pointer to
  `DEVELOPMENT.md` §3's full, current 31-package inventory and a statement that the only remaining
  boundary is `nexus_core`'s own dependency-direction rule.
- **Three new sections added**, per the governing prompt's explicit list: §7 Documentation expectations
  (when a PR must also update docs, examples, benchmarks, or an ADR — and explicitly, when it must *not*
  edit one), §8 Pull request process (branch protection's real behavior, including the disclosed case from
  `V2_RELEASE_EXECUTION_REPORT.md` where unresolved review threads blocked a merge even after the
  underlying code had changed), §9 Issue reporting (grounded in the same "never guess, never invent
  requirements" norm v1's own `CONTRIBUTING.md` already states, made explicit for v2 too).

`docs/development/DEVELOPMENT.md` (reviewed per the prompt's explicit "review DEVELOPMENT.md" instruction):

- **§3's package layout table was six packages; it is now all 31**, grouped by the four architectural
  planes the root README's own capability table uses (Reasoning & Grounding, Planning & Governance,
  Execution, Post-Execution, plus the Scheduler/Approval/Operations/Human-Interaction group and the
  application-layer consumer packages) — verified directly against `ls nexus_*/` before writing, not
  copied from an earlier document.
- **§6's quality-gate table previously implied `make check` and CI check the same thing.** Corrected with
  the same 20-vs-31-package disclosure as `CONTRIBUTING.md`, cross-referenced rather than duplicated in
  full (see §5 below on how the initial draft's duplication was found and trimmed).
- **§8's Windows-notes manual command example only listed 6 packages** (stale, matching the old §3). Fixed
  to point at the Makefile's actual `PACKAGES`/`TESTS` variables directly and at `core-ci.yml`'s real
  command for full-scope verification, rather than hand-copying a list that had already drifted once.
- **Four new sections added**, per the governing prompt: §9 Adding a new package (states plainly that no
  single source of truth exists today — three files must be updated by hand — a real, disclosed gap, not a
  hidden expectation), §10 Adding an ADR (the numbering-collision check, the "never retrofit" rule, citing
  ADR-009 as the real precedent), §11 Documentation workflow (pointer to the new
  `docs/development/DOCUMENTATION_GUIDE.md`), §12 Release workflow (pointer to the new
  `docs/releases/README.md`).

`docs/development/TESTING.md` — a lighter touch: added §2.1 stating explicitly that every package built
after Phase 6 (`nexus_execution` onward) follows the same per-layer test discipline already described, under
its own mirrored `tests/unit/<package>/` directory, rather than rewriting each layer's description to the
same depth (a proportionate choice — the existing prose for Phases 1–6 remains accurate and didn't need
touching). Also disclosed the coverage-gate's actual 20-package scope and named the two packages
(`nexus_repository`, `nexus_scheduler`) that currently sit below the 95% floor, sourced directly from
`docs/v2/P17_PRODUCTION_READINESS_REPORT.md` rather than left as an implicit gap.

The root-level `CONTRIBUTING.md`/`DEVELOPMENT.md`/`ONBOARDING.md` (v1) were reviewed per the "Read First"
instruction but intentionally left with only the polish fixes in §6 below — they are correctly scoped to
v1, already carry the cross-reference banners earlier phases added, and rewriting v1's own content is
outside a v2-focused developer-experience phase.

---

## 4. Release Governance

`docs/releases/README.md` — new, and deliberately grounded in what this repository has actually done, not
an idealized process:

- **Versioning**: the real, slightly unusual one-`pyproject.toml`-version-for-two-products constraint,
  and the semver convention inferred from the actual release history (`v1.0.0`→`v1.0.1` patch,
  `v1.0.1`→`v1.1.0` minor, `v1.x`→`v2.0.0` an independent-product jump, not a same-product major).
- **Release cadence**: stated plainly as **not fixed** — four releases across two products is not enough
  data to claim a cadence, and this report does not invent one.
- **The actual process**: the real five-milestone chain (Production Readiness → RC1 → RC2 → Release
  Readiness → Release Execution), including RC1's own real GA-recommendation downgrade and RC2's real
  restoration of it — presented as evidence the process catches its own mistakes, not smoothed over.
- **Commit/merge/tag mechanics**: sourced directly from `RC1_PRODUCTIZATION_REPORT.md` §1 and
  `V2_RELEASE_EXECUTION_REPORT.md` §1–3 (isolated-diff commit discipline, regular-merge-commit-only
  history, the real branch-protection block this repository actually hit).
- **Deprecation policy and support expectations**: explicitly stated as **not formally defined today**,
  with only the one real, current fact documented (v1/v2 are fully independent, so one's support posture
  doesn't cascade to the other) — per this phase's own instruction not to invent governance.

---

## 5. Documentation Governance

`docs/development/DOCUMENTATION_GUIDE.md` — new, and built entirely by extracting the conventions this
seven-phase initiative already followed and enforced, each cited to the phase report where it was
established: writing style (state facts, disclose gaps, one authoritative source per fact), diagram
conventions (ASCII baseline, Mermaid where it adds clarity), Mermaid usage (bracket-balance and
render-check, discussed the same way Phase 4/5/6 actually validated their own diagrams), cross-link
expectations (verify before committing, link new content from its natural index), evidence requirements (no
invented APIs, no invented history — citing Phase 5's ADR-005/006 investigation as the concrete example of
this discipline in practice), benchmark rules (cite the source report, no new measurements without
instruction, state methodology caveats every time — directly matching `docs/benchmarks/README.md`'s own
practice), and ADR update rules (never edit a ratified decision, keep the index current, check the
numbering-collision table first).

This document is deliberately retrospective — every rule cites where it was already applied, so future
documentation work has a real, demonstrated precedent to follow rather than an aspirational style guide no
prior phase actually lived up to.

---

## 6. Validation Results

- **Every tutorial references a runnable example.** Verified by cross-checking all ten tutorials' example
  paths against `examples/`'s actual directory names — all ten resolve to real, already-validated (Phase 4)
  example directories.
- **Every internal link resolves.** Two link-resolution passes were run: one over every file created or
  edited this phase (24 files, tutorials + getting-started + releases + development guides + the three root
  v1 files + `docs/README.md`/`docs/v2/README.md`/`docs/architecture/README.md`), and a full-repository
  polish audit (dispatched as a background agent, 313 markdown files, 298+ relative links checked) — both
  found **zero broken links**, before and after this phase's own edits.
- **Repository polish audit findings and fixes applied** (Phase 7G):
  - **Heading hierarchy**: `docs/v2/README.md` used a repeated top-level `#` for nine section headings
    after its own title (Overview, Vision, Evolution, Design Philosophy, Capability Layers, Architectural
    Goals, Document Structure, Design Status, North Star) instead of `##` — **fixed**: demoted to `##`,
    and their own correctly-nested `##` subsections demoted to `###` in the same pass, so the file now has
    exactly one H1 and a consistent H2/H3 hierarchy.
  - **Heading capitalization**: root `README.md`'s "Why Nexus exists" (sentence case) next to "Why Nexus is
    Different" (Title Case, same construction) — **fixed** to Title Case for consistency. Root
    `DEVELOPMENT.md`'s three Troubleshooting subheadings and root `ONBOARDING.md`'s one sentence-style
    subheading, both inconsistent with the rest of their own file's Title Case convention — **fixed**.
  - **Code-fence language tags**: three untagged pattern blocks (branch-naming and commit-message examples
    in root `CONTRIBUTING.md`; the commit-message-format block in root `DEVELOPMENT.md`) inconsistent with
    adjacent, similarly-shaped blocks in the same files that *were* tagged ` ```bash ` — **fixed**, tagged
    ` ```text ` (these are patterns, not literally-runnable shell commands, so `text` rather than `bash`).
  - **Duplicated content, the one real drift risk found**: the "make check covers 20 of 31 packages, CI
    covers all 31" fact was independently written out in full in both `docs/development/CONTRIBUTING.md`
    §4 and `DEVELOPMENT.md` §6 — **fixed**: trimmed `CONTRIBUTING.md`'s copy to a short pointer, made
    `DEVELOPMENT.md` §6 the single source of truth for the exact package list.
  - **Badges**: audited and found fully consistent — every badge's link target exists, and the CI badge's
    branch/workflow-file reference matches the actual repository state (confirmed via `git remote show
    origin`). No fix needed.
  - **Markdown formatting** (bullets, table column counts, trailing whitespace): audited and found no
    inconsistencies beyond the intentional hard-line-break trailing spaces in `docs/v2/README.md`'s status
    line (valid Markdown, left as-is).
  - **Not fixed, and explicitly not in scope**: the audit separately found that v1's own root
    `CONTRIBUTING.md` and `DEVELOPMENT.md` already duplicate their own "Testing" and "Git Workflow" content
    against *each other* (a v1-internal issue, predating this initiative and unrelated to the v2 developer
    experience this phase's mandate covers) — noted here for a future v1-focused pass, not corrected by
    this phase.
- **No implementation, tooling, or architecture change was made.** `git status --short` after this phase's
  edits shows only Markdown files under `docs/tutorials/`, `docs/getting-started/`, `docs/releases/`,
  `docs/development/`, plus the root `README.md`/`CONTRIBUTING.md`/`DEVELOPMENT.md`/`ONBOARDING.md` and
  `docs/README.md`/`docs/v2/README.md`/`docs/architecture/README.md` — filtering for `nexus_*/`, `tests/`,
  `scripts/`, `pyproject.toml`, `Makefile`, `ruff.toml`, and `.github/` returns nothing.

---

## 7. Documentation Initiative Summary

Seven phases, in order:

1. **Master Plan** — full audit of ~526 markdown files across two unrelated codebases sharing one
   repository; identified the navigability, currency, and naming-collision problems every later phase
   fixed.
2. **Foundation & Information Architecture** — `docs/README.md`, root README v2 acknowledgment, naming-
   collision banners, stray-file relocation.
3. **Public Repository & Flagship Identity** — the flagship root `README.md` rewrite, `docs/architecture/README.md`
   portal, `docs/runtime/README.md`.
4. **Production Examples & Reference Workflows** — `examples/`, ten runnable, executed-not-just-reviewed
   examples; caught three real platform-adjacent bugs in the process.
5. **Architectural Decision Integrity** — full ADR audit, the ADR-005/006 investigation (evidence-first,
   no fabricated history), the expanded `adr/README.md` canonical index, the ADR-010 numbering collision
   found and disclosed.
6. **Benchmarks, Performance & Operational Evidence** — `docs/benchmarks/`, every measured value re-
   published with provenance, explicit "What Nexus Has Not Benchmarked" honesty section.
7. **Developer Experience, Tutorials & Project Governance** (this phase) — `docs/tutorials/`,
   `docs/getting-started/`, contributor/development guide currency fixes, `docs/releases/README.md`,
   `docs/development/DOCUMENTATION_GUIDE.md`, and a repository-wide polish pass.

**Net result:** a new engineer can now go from `git clone` to a first successful run in under 15 minutes
(`docs/getting-started/`), learn the platform concept-by-concept against real, runnable code
(`docs/tutorials/`, `examples/`), understand the full architecture and why every major decision was made
(`docs/architecture/README.md`, `adr/README.md`), see exactly what's been measured and what hasn't
(`docs/benchmarks/`), contribute a change that meets the platform's actual current standards
(`docs/development/CONTRIBUTING.md`, `DEVELOPMENT.md`, `TESTING.md`), and understand how releases are cut
and maintained (`docs/releases/README.md`) — all without needing to ask an original author.

**Across all seven phases, zero implementation, test, or CI files were modified.** Every change was
documentation, and every claim in it was verified against real source, a real report, or a real,
re-executed command before being written down.

This concludes the Documentation Initiative. Per the governing prompt: stopping here.
