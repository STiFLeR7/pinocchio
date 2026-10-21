# Release Governance

How Nexus is versioned, released, and maintained long-term — documented from **this repository's own
actual practice**, not an idealized process. Where no formal policy exists yet, this page says so plainly
rather than inventing one.

## Versioning

**One `pyproject.toml` version field describes the one distributable wheel** — both Nexus v1 (`nexus/`)
and all 32 Nexus v2 (`nexus_*`) packages ship together in a single artifact, and share that one version
string. This is a real, slightly unusual constraint (most projects with two independent codebases would
version them separately) — documented explicitly in `docs/v2/V1_RELEASE_READINESS_REPORT.md` because it
was flagged as a four-way disagreement (`pyproject.toml`, 24-of-31 packages, 7 unversioned packages, and
`CHANGELOG.md` all disagreeing) and resolved by making every one of them read the same value.

Each v2 package additionally self-declares its own `__version__` in `<package>/__init__.py`, verified
individually to match `pyproject.toml` at every release (`docs/v2/V2_RELEASE_EXECUTION_REPORT.md` §5).

**Semantic versioning** is the convention followed in practice, inferred from the project's own release
history and `CHANGELOG.md`'s Keep a Changelog format:

- **Patch** (`v1.0.0` → `v1.0.1`, "Alignment") — bug fixes and consistency corrections, no new capability.
- **Minor** (`v1.0.1` → `v1.1.0`, "Containment") — additive new capability (e.g. the Scheduler foundation),
  no breaking change to existing behavior.
- **Major-shaped jump** (`v1.x` → `v2.0.0`, "Constitutional Spine") — not a semver bump of the same product
  in the strict sense. v2 is an independent, from-scratch rebuild (`nexus_*`, zero shared code/schema/
  process with `nexus/`) that happens to share this repository and one version field. Treat "2.0.0" as
  marking "the constitutional platform's first release," not "an incompatible v1.x change" — because
  nothing in v1 changed as a result of it.

## Release cadence

**No fixed release cadence exists, and none is claimed here.** Releases have happened when a milestone's
own evidence gate was fully green (full test suite, `mypy --strict`, `ruff`, wheel build, and — for v2.0.0
specifically — a full architectural-correctness audit chain: `P17_PRODUCTION_READINESS_REPORT.md` → RC1 →
RC2 → Release Readiness → Release Execution), not on a calendar schedule. The documented release sequence
is `v1.0.0` → `v1.0.1` → `v1.1.0` → `v2.0.0` → `v2.5.0`. No fixed cadence is inferred from this small
history across two products.

## v2.5.0 release record

The stable minor release is titled **Nexus v2.5.0 — Accountable Goal Execution**. Its evidence
and release record are collected in [the release report](V2_5_RELEASE_REPORT.md); the controlled
five-case technical pilot is detailed in [the Phase 6 review](../phase6/RELEASE_REVIEW.md). The pilot
supports only the bounded claims in those reports: three useful accepted repairs, one detected failure,
one `requires_review` outcome, and no reported false denials. It does not establish arbitrary real-repository
reliability or autonomous repair. The report distinguishes recorded pilot checks from CI verification on the
pushed release commit.

## The actual release process (as practiced for `v2.0.0`)

This is what happened, not an aspirational checklist — five sequential milestones, each producing its own
report:

1. **Production Readiness audit** (`docs/v2/P17_PRODUCTION_READINESS_REPORT.md`) — certifies architectural
   soundness, names every GA blocker found.
2. **RC1** (`docs/v2/RC1_PRODUCTIZATION_REPORT.md`) — closes blockers, adds the production entrypoint,
   fixes the Scheduler's O(n²) ceiling, proposes ADR-009. Downgrades its own GA recommendation when its
   own pre-merge adversarial review finds a new, more severe defect (risk #12) — a real example of the
   process catching itself, not glossing over an inconvenient finding.
3. **RC2** (`docs/v2/RC2_EXECUTION_IDENTITY_REPORT.md`) — closes risk #12 (cross-goal execution-identity
   corruption), restores the GA recommendation RC1 downgraded.
4. **Release Readiness** (`docs/v2/V1_RELEASE_READINESS_REPORT.md`) — repository/consistency audit,
   resolves the four-way version disagreement, adds `LICENSE`, produces the exact commit plan to execute.
   Explicitly commits nothing itself — working-tree-only, by design, so a review gate exists before history
   is written.
5. **Release Execution** (`docs/v2/V2_RELEASE_EXECUTION_REPORT.md`) — executes the commit plan exactly as
   written, merges, tags, and re-verifies everything against the actual tagged commit (not just the
   working tree). Found one new fact even at this stage (`ruff format --check` had never been separately
   verified) and disclosed it rather than quietly folding it in.

**Commit discipline:** each release groups changes into small, single-purpose, Conventional-Commits-
formatted commits (see `docs/v2/RC1_PRODUCTIZATION_REPORT.md` §1 for the full worked example, including how
a fix that landed in a file with no prior commit to diff against was still isolated into its own reviewable
diff by reconstructing the pre-fix state from session history, rather than bundled invisibly into a feature
commit).

**Merge strategy:** every merge to `master` in this repository's history is a regular merge commit
(`gh pr merge N --merge`) — no squash or rebase merges exist, and `V2_RELEASE_EXECUTION_REPORT.md` §2
explicitly confirms this pattern was followed for `v2.0.0`, not just assumed.

**Tag verification:** an annotated tag is confirmed to point at the actual merge commit
(`git rev-parse <tag>^{commit}`), confirmed to be an ancestor of the pushed `master`
(`git merge-base --is-ancestor`), and confirmed not to collide with an existing tag before pushing.

**CI as the actual gate, not a formality:** a release is not considered complete until CI is green on the
real merge commit — not just on a pre-merge branch — across every required job. `V2_RELEASE_EXECUTION_REPORT.md`
§2 documents a real case where branch protection blocked the merge until two unresolved automated-review
threads were addressed, even though the underlying defects they described had already been fixed.

## Deprecation policy

**No formal deprecation policy exists today**, and this page does not invent one. The one real, current
fact worth stating plainly: **v1 and v2 are fully independent** (zero shared code, schema, or process in
either direction, confirmed by audit in `docs/v2/P17_PRODUCTION_READINESS_REPORT.md`), so a support or
deprecation decision about one has no effect on the other. Any future deprecation policy for either product
is a product decision, not something this documentation initiative is positioned to make on the team's
behalf.

## Support expectations

Also not formally defined today. What can be said honestly, grounded in what's actually shipped:

- **v2.0.0's known limitations are disclosed, not hidden** — no v1→v2 data migration tool, an unversioned
  durable schema, ADR-009 filed but unratified, two subsystems built but not yet wired to a live entrypoint
  (see `CHANGELOG.md` [2.0.0]'s own "Known Limitations" section for the authoritative, current list).
- **Greenfield-only deployment is the current, explicit scope for v2** — `docs/v2/RC1_MIGRATION_GUIDE.md`
  states this as the operative rule, not an oversight.
- Beyond these disclosed facts, this page makes no claim about how long a given release will be supported,
  patched, or maintained — stating an SLA or support window this repository has not actually committed to
  would be exactly the kind of invented governance this phase's instructions forbid.

## Where release evidence actually lives

`CHANGELOG.md` (the durable, versioned summary), the [v2.5.0 release report](V2_5_RELEASE_REPORT.md),
and, per release, the full audit chain under `docs/v2/`
(`P17_PRODUCTION_READINESS_REPORT.md`, `RC1_PRODUCTIZATION_REPORT.md`, `RC2_EXECUTION_IDENTITY_REPORT.md`,
`V1_RELEASE_READINESS_REPORT.md`, `V2_RELEASE_EXECUTION_REPORT.md`) — this page is an index and summary of
that evidence, not a replacement for it.
