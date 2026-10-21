# Nexus Documentation — Start Here

This repository holds **two independent, non-interoperating codebases** that share one git history and
one `pyproject.toml`, and nothing else (zero imports in either direction, no shared schema, no shared
process):

- **v1** (`nexus/`) — released as `v1.0.0` ("Operational Intelligence"), currently in the `v1.0.1`
  "Alignment" line. A Discord-fronted AI orchestration control plane.
- **v2** (`nexus_*`, 32 packages) — `v2.5.0` ("Accountable Goal Execution") is the stable minor release.
  It extends the event-sourced constitutional reasoning spine and remains architecturally and operationally
  independent of v1.

Most documentation confusion in this repository comes from not knowing which of the two a given file
describes. This page exists to answer that in one lookup.

**Landed here from the root [README.md](../README.md)?** That page is v2's front door. This page is the
full map — read on if the README's links didn't already answer your question.

## "I want to..."

| ...work on v1 (`nexus/`) | ...work on v2 (`nexus_*`) |
|---|---|
| Read [ONBOARDING.md](../ONBOARDING.md) first | Start at [docs/getting-started/README.md](getting-started/README.md) (first run in under 15 minutes), then [docs/internals/WALKTHROUGH-v2.md](internals/WALKTHROUGH-v2.md) |
| Contribute: [CONTRIBUTING.md](../CONTRIBUTING.md) (root) | Contribute: [docs/development/CONTRIBUTING.md](development/CONTRIBUTING.md) |
| Set up locally: [DEVELOPMENT.md](../DEVELOPMENT.md) (root) | Set up locally: [docs/development/DEVELOPMENT.md](development/DEVELOPMENT.md) |
| Design docs: [docs/v1/](v1/) (`00_BRIEF.md` onward) | Design docs: [docs/v2/](v2/) (start at [docs/v2/README.md](v2/README.md)) |
| Current status: [blueprint/STATUS.md](../blueprint/STATUS.md), [blueprint/ROADMAP.md](../blueprint/ROADMAP.md) | Release record: [v2.5.0 report](releases/V2_5_RELEASE_REPORT.md), [Phase 6 pilot review](phase6/RELEASE_REVIEW.md) |
| Decision records: [blueprint/DECISIONS/](../blueprint/DECISIONS/) | Decision records: [adr/README.md](../adr/README.md) (`ADR-001`–`004`, `007`–`009`) |
| — | Full architecture portal (every subsystem, one page): [docs/architecture/README.md](architecture/README.md) |
| — | As-built engineering notes per subsystem: [docs/runtime/README.md](runtime/README.md) |
| — | Learn by running examples in a guided order: [docs/tutorials/README.md](tutorials/README.md) |
| — | What's actually been measured: [docs/benchmarks/README.md](benchmarks/README.md) |
| — | How releases are cut and maintained: [docs/releases/README.md](releases/README.md) |
| — | House style for writing documentation: [docs/development/DOCUMENTATION_GUIDE.md](development/DOCUMENTATION_GUIDE.md) |
| Run tests: `pytest` (see root [DEVELOPMENT.md](../DEVELOPMENT.md)) | Run tests: `make check` (see [docs/development/TESTING.md](development/TESTING.md)) |

## Why the file layout looks the way it does

- **Root-level `CONTRIBUTING.md`/`DEVELOPMENT.md` are v1's.** `docs/development/CONTRIBUTING.md`/
  `DEVELOPMENT.md`/`TESTING.md` are v2's. Same filenames, disjoint content, one small banner at the top
  of each pointing to its counterpart. They were not merged or renamed because both are cited by exact
  path from a large number of other documents (including historical `blueprint/` audit reports that cite
  specific line numbers) — renaming would have broken more references than the naming collision itself
  causes confusion.
- **`docs/v2/`** (169 files) is the frozen target architecture, written before v2's implementation began
  and preserved as the design record — now annotated as released, not superseded.
- **`docs/runtime/`** (64 files) is *not* a duplicate of `docs/v2/` — it's the as-built engineering record
  for the packages that implement that design, some of it cited directly from production code. See
  [docs/runtime/README.md](runtime/README.md) for the full explanation and per-subsystem index.
- **`docs/v1/`** (15 files) is v1's own, separate design brief — no relationship to `docs/v2/` or
  `docs/runtime/` beyond sharing a repository.
- **`docs/internals/`** holds code-level tours (as opposed to `docs/v2/`'s design-intent docs or
  `docs/runtime/`'s per-subsystem engineering notes) — currently just
  [WALKTHROUGH-v2.md](internals/WALKTHROUGH-v2.md), a single cross-cutting tour of the v2 codebase.
- **`adr/`** (7 files: `ADR-001`–`004`, `007`–`009`, plus [`adr/README.md`](../adr/README.md) as an
  index) holds v2's ratified/proposed Architecture Decision Records. `blueprint/DECISIONS/` holds v1's
  own, separately-numbered ADR series — the two are intentionally on different numbering tracks (noted
  directly in `adr/ADR-007-persistence-authority.md`).
- **`docs/architecture/`** is new: a single portal page (no separate files) indexing every subsystem's
  architecture documentation from one place, for readers who want the whole picture rather than one
  subsystem at a time.
- **`blueprint/`** (259 files) is v1's "living memory" system — status, roadmap, decisions, audits, and
  per-Action-Point implementation history. It predates v2 and remains v1-specific.

## Reports and release history

- v2.5.0 release evidence and Phase 1–6 scope: [docs/releases/V2_5_RELEASE_REPORT.md](releases/V2_5_RELEASE_REPORT.md).
- v2's release evidence: `docs/v2/RC1_PRODUCTIZATION_REPORT.md`, `docs/v2/RC2_EXECUTION_IDENTITY_REPORT.md`,
  `docs/v2/V1_RELEASE_READINESS_REPORT.md`, `docs/v2/V2_RELEASE_EXECUTION_REPORT.md`.
- v1's release/audit history: `blueprint/onboarding/` (the accepted v1.0.0 onboarding audit),
  `blueprint/implementations/v1.0.1/` (the "Alignment" pass, including the documentation-alignment work
  that first surfaced many of the navigability issues this page now addresses).
- The documentation initiative itself: `docs/DOCUMENTATION_MASTER_PLAN.md` (the audit and full plan),
  `docs/DOCUMENTATION_PHASE2_REPORT.md` (foundation/navigation), `docs/DOCUMENTATION_PHASE3_REPORT.md`
  (public-repository/README), `docs/DOCUMENTATION_PHASE4_REPORT.md` (the example library),
  `docs/DOCUMENTATION_PHASE5_REPORT.md` (ADR audit and traceability), `docs/DOCUMENTATION_PHASE6_REPORT.md`
  (benchmarks and operational evidence), `docs/DOCUMENTATION_PHASE7_REPORT.md` (tutorials, developer
  experience, and release/documentation governance — the initiative's final phase).
