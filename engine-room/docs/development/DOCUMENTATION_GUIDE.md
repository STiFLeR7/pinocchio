# Documentation Contribution Guide

How documentation should evolve in this repository, extracted from the conventions this repository's own
seven-phase documentation initiative actually followed (`docs/DOCUMENTATION_MASTER_PLAN.md` through
`docs/DOCUMENTATION_PHASE7_REPORT.md`). These are real, already-applied rules, not aspirational ones — every
rule below cites the phase report where it was established and enforced.

## 1. Writing style

- **State facts, don't market them.** "Deterministic, not best-effort" (a real, checkable claim) over
  "blazing fast" (an unfalsifiable one). `docs/benchmarks/README.md`'s "Performance Philosophy" section is
  the reference example.
- **Cite, don't paraphrase from memory.** Every API name, field name, or measured number should be verified
  against the actual source (code, test, or report) before being written down — this repository's own
  documentation work has caught real mistakes exactly this way (wrong field names in two examples, an
  algorithmic bug in a third — `docs/DOCUMENTATION_PHASE4_REPORT.md` §3).
- **Disclose gaps instead of omitting them.** A known limitation, an unmeasured scale, or a stale reference
  should be named explicitly (see `docs/benchmarks/README.md`'s "What Nexus Has Not Benchmarked" and
  `docs/development/DEVELOPMENT.md` §6's `make check`-vs-CI scope disclosure) — silence reads as "covered,"
  which is a stronger and often false claim.
- **One document, one authoritative source per fact.** If two documents could both describe the same
  thing, one should link to the other rather than both maintaining their own copy — `docs/architecture/README.md`'s
  own closing line states this explicitly: "if a linked document and this portal ever disagree, the linked
  document is correct — file it as a documentation bug."

## 2. Diagram conventions

- **ASCII-in-code-fences is this repository's baseline convention** (legible, git-diffable, no rendering
  dependency) — do not replace it wholesale.
- **Mermaid supplements ASCII where it clarifies something ASCII can't** — architecture portals, dependency
  graphs, timelines (see `docs/architecture/README.md`, `adr/README.md`'s dependency graph, and
  `docs/DOCUMENTATION_PHASE5_REPORT.md`'s ADR timeline for real examples). Don't add a Mermaid diagram
  that repeats what an adjacent ASCII block already says just as clearly.

## 3. Mermaid usage

- **Every Mermaid block must be bracket-balanced and must actually render** — this was a real, checked
  validation step in Phases 4–6 (12+ diagrams checked for bracket balance in `docs/DOCUMENTATION_PHASE4_REPORT.md`
  §4). Before committing a new one, count opening/closing brackets by eye or paste it into a Mermaid-aware
  previewer.
- **Prefer `flowchart` for structure/dependency relationships**, `timeline` for chronological evolution
  (see `docs/DOCUMENTATION_PHASE5_REPORT.md` §6 for a real `timeline` block) — pick the diagram type that
  matches what you're actually showing, not the one you're most used to.
- **Label edges when the relationship type matters** (`-.consistent with.->` vs. a plain `-->`) — a
  dependency graph that doesn't distinguish "depends on" from "is consistent with" loses information a
  reader needs (see `adr/README.md`'s dependency graph for the pattern).

## 4. Cross-link expectations

- **Link by relative path, and verify it resolves before committing.** Every phase of this initiative ran
  a link-resolution check before calling documentation work done (`docs/DOCUMENTATION_PHASE4_REPORT.md` §4:
  "every relative link... checked against the filesystem, with anchor fragments correctly stripped before
  the check"). A broken link in new documentation is a defect, not a typo to fix later.
- **New documents get linked FROM their natural entry point**, not left orphaned. A new tutorial, example,
  or benchmark doc that isn't reachable from `docs/README.md`, the root `README.md`, or the relevant index
  page (`docs/tutorials/README.md`, `examples/README.md`, `docs/benchmarks/README.md`) is effectively
  undiscoverable — add the link in the same PR that adds the content.
- **Don't duplicate a link's target content at the link site.** State what the reader will find and why
  it's relevant, then link — don't re-explain it and link, which is exactly the kind of drift risk this
  guide exists to prevent.

## 5. Evidence requirements

- **No invented APIs, ever.** Every code example must call a real, released, already-tested symbol —
  verified directly against source before being written, never assumed from a prior design doc or an
  earlier session's memory (`docs/DOCUMENTATION_MASTER_PLAN.md`'s and every subsequent phase's own
  standing rule).
- **No invented history.** An architectural claim ("this was ratified," "this decision resolved that gap")
  must be traceable to a real ADR, commit, or report — `docs/DOCUMENTATION_PHASE5_REPORT.md`'s entire
  ADR-005/006 investigation exists because this rule was taken seriously: evidence was gathered *before*
  any conclusion was drawn, and no ADR was fabricated to fill the gap it found.
- **Run it, don't just review it.** Any code presented as runnable (an example, a tutorial command) must
  actually be executed before being committed — reviewing code by eye misses real bugs that running it
  catches (three real, distinct bugs were caught exactly this way in `docs/DOCUMENTATION_PHASE4_REPORT.md`
  §3, none of which a careful read would have found).

## 6. Benchmark rules

`docs/benchmarks/` is evidence-only, never marketing:

- **Every number must cite its source report and section.** No figure is recomputed, rounded differently,
  or extrapolated from what the source report actually states (`docs/DOCUMENTATION_PHASE6_REPORT.md` §7's
  own validation standard).
- **No new measurements without explicit instruction.** This directory re-publishes released, already-run
  evidence; it is not where new performance experiments get run and reported for the first time as part of
  a documentation pass.
- **State the methodology's own caveats, every time** (single-machine, single-run, order-of-magnitude not
  a calibrated SLA, ±10–15% run-to-run variance) — repeat them at the top of every new benchmark document
  rather than assuming a reader read the caveat once elsewhere.
- **State what was NOT measured, explicitly**, whenever a benchmark's scale or scope could otherwise be
  read as broader than it is (`docs/benchmarks/README.md`'s "What Nexus Has Not Benchmarked" section is the
  reference example — silence about scale limits reads as an implied, unearned claim).

## 7. ADR update rules

- **Never edit a ratified ADR's Decision section to match new code.** If the Constitution and shipped code
  disagree, that's a finding to raise (an issue, or a new ADR proposing resolution — see
  `docs/development/DEVELOPMENT.md` §10) — `ADR-009-runtime-selection-ownership.md` is the real, live
  example of exactly this situation, filed as **Proposed**, not silently merged into an earlier ADR.
- **`adr/README.md`'s index is the canonical navigation page** (established in
  `docs/DOCUMENTATION_PHASE5_REPORT.md` §4) — a new or status-changed ADR must be reflected there in the
  same PR: title, status, date, motivation, impacted subsystems, related ADRs, implementation references,
  release introduced.
- **Check the numbering-collision table before assigning a number.** v2's `adr/` series and v1's
  `blueprint/DECISIONS/` series are independently numbered by design; a new ADR should not silently
  introduce a new, undocumented collision the way ADR-010 did before Phase 5 found and disclosed it.
- **A missing ADR number is a gap to investigate, never a gap to fabricate around.** Evidence first, always
  — did the file ever exist (check git history), what was it actually supposed to decide (read every
  reference in its original context, not a later summary of it), was its substance carried out anyway. Only
  after that investigation does "write a catch-up ADR" become a defensible option, and even then it should
  be labeled retrospective, not backdated silently.
