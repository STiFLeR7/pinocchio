# Nexus v2.0 — Release Report

This report records the disciplined production release of Nexus v2.0: what was verified, what was
tagged, what was published, and what was deliberately left out. No architecture, feature, or
documentation work was performed as part of this release — it executes exactly what the phase 1–7
documentation programme and the P0–P17/RC1/RC2 constitutional engineering program already built.

## Commit

- **Released commit:** `c5028261a6f4304270ae7e121baccfd188e3e761`
- **Branch:** `master` (== `origin/master` at release time)
- **Release commit's own change:** `chore(release): ruff format fix for v2.0 tutorial examples` —
  a 3-file, 11-line formatting fix (see "Repository audit" below for why it was needed).
- **7 commits of substantive content precede it** (already committed and pushed before this release
  began): the phase 1–7 documentation programme (`3006098`…`1ef7d92`), on top of the original
  `v2.0.0` tag base (`07097ac`, the P0–P17/RC1/RC2 constitutional engineering program).

## Tag

- **Tag:** `v2.0.0` (annotated), target commit `c502826`.
- The `v2.0.0` tag previously existed pointing at `07097ac` (23 Jul 2026) — the commit at which the
  constitutional platform itself was first tagged stable, before the documentation programme.
  Because the 8 commits since then are exclusively documentation (no code, no version bump), and per
  explicit instruction from the repository owner, the existing `v2.0.0` tag was deleted and
  recreated at the current HEAD rather than minted as a new version — `pyproject.toml` and every
  `nexus_*` package's `__version__` already read `2.0.0` consistently, so no version number changed.
- Tag message includes a summary, the release highlights, and the validation summary (below).

## Repository audit

- Working tree was not clean at the start of this release: 3 modified files and 4 untracked paths
  from a prior, separate task (P0 "first real user" — a real-provider LLM Runtime Adapter, a
  terminal CLI, and an approval-gate demo). None of these are referenced anywhere in the v2.0
  release scope. **Per explicit instruction, they were left entirely out of this release** — not
  committed, not tagged, not included in the wheel build. They remain as uncommitted working-tree
  changes for a separate commit later.
- No TODO/FIXME/XXX/HACK, no debug `print`/`console.log`/`pdb`/`breakpoint()` calls, no secret-like
  patterns (API keys, passwords, PEM blocks), and no tracked generated artifacts (`__pycache__`,
  `.pyc`, `.egg-info`, cache dirs, `.db` files) were found in any file changed since the prior
  `v2.0.0` tag. The `print()` calls found are all intentional narration output in `examples/*/run.py`
  tutorial scripts — expected, not debug logging.
- One real issue was found and fixed: `examples/03-policy-governance/run.py` (a new file added by
  the documentation programme) failed both `ruff check` (unsorted imports) and, together with two
  sibling example files (`07-approval-exchange`, `09-recovery`), `ruff format --check`. Fixed with
  `ruff check --fix` / `ruff format` restricted to exactly those 3 files, verified clean, and
  committed as this release's only commit.

## Version validation

`pyproject.toml` (`version = "2.0.0"`), every `nexus_*` package's `__version__`, the README badge,
and `CHANGELOG.md`'s `[2.0.0]` entry all agree on `2.0.0`. No inconsistency found; no change needed.

## Validation suite results

Run against the release commit, using the exact commands `core-ci.yml` runs in CI:

| Check | Command scope | Result |
|---|---|---|
| Ruff lint | all 31 `nexus_*` packages + their unit/integration tests | clean |
| Ruff format | same scope | clean (after the 3-file fix above) |
| MyPy `--strict` | 30 v2 packages | clean — 388 source files, 0 errors |
| Pytest | v2 unit + integration suites | 2941 passed, 1 skipped, 175 warnings |
| Coverage | `--cov-fail-under=95` gate | 97.97% achieved |
| Build | `uv build` (sdist + wheel) | succeeds, from a **clean checkout of the release commit** |

The skipped test is `tests/integration/test_runtime_vertical_slice.py`'s opt-in live-Claude smoke
test (`NEXUS_CLAUDE_SMOKE=1` + an authenticated `claude` CLI on PATH) — expected to skip in this
environment, not a failure.

**Wheel build note:** the first build (before the P0 files were confirmed out of scope) picked up
the uncommitted `pyproject.toml` change from the working tree and leaked the unreleased
`nexus_runtime_llm` package into the wheel, because `uv build` builds from the working directory,
not from git. The working tree was stashed, the build was re-run against a clean checkout of the
release commit, and the resulting wheel was confirmed to contain none of the P0 files before the
stash was restored. Both CI workflows (`Core CI`, `Nexus CI`) also ran and passed against the
pushed commit independently, confirming this was not an artifact of the local build environment.

## GitHub Release

- Published at <https://github.com/STiFLeR7/nexus/releases/tag/v2.0.0>, not a draft, not a
  prerelease.
- Body: highlights (Constitutional AI Control Plane, deterministic execution, policy-governed
  autonomy, replay & restart, runtime abstraction, Human Interaction, Scheduler, Operations,
  documentation, examples, tutorials, benchmarks), links to README/Documentation/Architecture/
  Examples/Tutorials at the `v2.0.0` ref, the validation summary above, and the Known Limitations
  section below, reproduced verbatim — no roadmap items were invented for the release notes.

## Post-release audit

- `git ls-remote --tags origin v2.0.0` → tag present remotely, target commit `c502826`.
- `gh release view v2.0.0` → published, not draft, not prerelease.
- `master` == `origin/master` == the tagged commit == `c502826`.
- `gh run list --branch master` → both `Core CI` and `Nexus CI` workflows report `completed` /
  `success` for this commit.
- Release assets: the GitHub Release itself (tag + auto-generated source archives); no wheel/sdist
  was uploaded as a release asset — none of the release phases requested one, and this release
  publishes source, not a packaged distribution.

## Known limitations (reproduced verbatim from `CHANGELOG.md`'s `[2.0.0]` entry)

- **No v1→v2 data migration tool.** The two strata use entirely different persistence models and
  remain fully isolated. `ADR-008-shadow-migration.md` documents a designed-but-unbuilt migration
  path. v2 today only supports a greenfield (empty durable log) start.
- **Durable schema is unversioned.** `nexus_infra/durable.py` uses `CREATE TABLE IF NOT EXISTS`
  only — idempotent bootstrap, no migration mechanism. A future schema change has no upgrade path
  for an existing durable file.
- **ADR-009 (INV-37 runtime-selection ownership) remains unratified** — Proposed status, carried
  forward from RC1.
- **Two frozen-contract candidates remain un-frozen** despite meeting the freeze trigger:
  `engineering_strategy` and `repository_understanding`.
- **`nexus_briefings` and `nexus_operator` remain unwired** into the running product (real, tested
  code; zero live callers) — flagged since P17, unchanged.
- A latent, not-currently-triggered identity-collision shape remains in `GraphNode.identifier` and
  its checkpoint reference — documented in `docs/v2/RC2_EXECUTION_IDENTITY_REPORT.md` §9 as a
  fast-follow, not a defect in the current code path.
- `ConstitutionalPipeline.execution_graph()`/`execution_state()` share the same un-scoped-
  reconstruction shape RC2 fixed on the restart path — dormant, documented as a fast-follow.
- Recovery is invoked with `checkpoint_ref=None` unconditionally — an independent INV-18 gap noted
  during RC2's audit, not in RC2's scope.

## Explicitly out of scope for this release

Per the P0 "First Real User" work performed separately (`nexus_runtime_llm`, `scripts/nexus_cli.py`,
`scripts/demo_approval_gate.py`, `docs/personal/`), none of it is part of `v2.0.0`. It remains
uncommitted in the working tree for the repository owner to commit on their own terms, outside this
release.
