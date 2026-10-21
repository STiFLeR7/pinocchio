# Contributing

> **This file covers Nexus v2** (`nexus_*` packages, the released constitutional platform). Working on
> v1 (`nexus/`) instead? See the root [CONTRIBUTING.md](../../CONTRIBUTING.md).

Thanks for working on Nexus. This guide covers the workflow and the standards
your change must meet. See [DEVELOPMENT.md](DEVELOPMENT.md) for setup and
[TESTING.md](TESTING.md) for the test approach.

---

## 1. Golden rule — the architecture is frozen

`nexus_core` implements a **ratified, frozen** architecture. The specs in
`docs/v2/`, the decisions in `adr/`, the logical specs in `contracts/`, and the
invariants in `docs/v2/99_ARCHITECTURAL_INVARIANTS.md` are authoritative.

**Do not** redesign abstractions, invent new ones, merge responsibilities,
bypass contracts, or edit an ADR as part of a code change. If your
implementation appears to conflict with the architecture, **stop and document
the conflict** (open an issue / ADR proposal) — do not silently change the
design. Code follows the architecture, not the other way around.

## 2. Branching & commits

- Branch from `master` (v2's mainline). `v1.2.0-planning`/`v1.1.0-planning` are
  **v1's** planning branches — do not branch v2 work from them; that naming
  collision has bitten this document before and is called out here so it
  doesn't bite you. PRs target `master`.
- Use **Conventional Commits**:

  ```
  feat(core): add X primitive
  fix(validation): correct relationship check for Y
  docs(development): clarify coverage policy
  test(domain): cover illegal Z transition
  chore(ci): pin ruff-pre-commit
  ```

- Keep commits focused and atomic. Do not bundle unrelated refactors.

## 3. Coding standards

These are enforced by the gate; internalizing them avoids churn:

- **Immutable domain objects.** Every model is a frozen Pydantic `DomainObject`
  with `extra="forbid"`. Sequence fields are `tuple`, not `list`.
- **References over embedding.** By-id pointers use `Reference`
  (`target_type` + `identifier`). No embedded object copies.
- **One canonical schema per object.** Enums live once in `contracts/`; never
  redefine them.
- **Dependency inversion.** Registries, events, and persistence are `Protocol`s.
  Higher layers depend on abstractions; the domain layer imports only
  `contracts`.
- **No infrastructure coupling** in `nexus_core`: no web framework, ORM,
  database, scheduler, runtime, or network. No global state or service locators.
- **Strict typing.** `mypy --strict` clean, PEP 695 generics, no stray `Any`,
  no unjustified `# type: ignore`.
- **Fail fast, never silently correct.** Validation raises on bad input.

## 4. The gate your PR must pass

Run locally before pushing:

```bash
make check
```

This must be green:

| Check | Requirement |
|-------|-------------|
| Ruff lint | `ruff check` clean (rules in `ruff.toml`) |
| Ruff format | `ruff format --check` clean |
| MyPy | `mypy --strict` clean (20 packages via `make check`; all 32 via CI — see the scope note below) |
| Tests | all pass |
| Coverage | branch coverage ≥ 95% (no artificial inflation) |
| Build | `uv build` succeeds |

**`make check`'s scope and CI's scope are not identical today — know the gap.**
`make check` only lints/type-checks 20 of the 32 v2 packages; Core CI covers all
32. **`DEVELOPMENT.md` §6 is the single source of truth for exactly which 12
packages that gap covers and why** — read it there rather than trusting a
second, independently-maintained list here. The short version: if your change
touches a package outside the Makefile's list, `make check` passing locally is
not sufficient evidence your change is clean — run CI's broader command
(`DEVELOPMENT.md` §8) or push and let CI catch it.

Core CI (`.github/workflows/core-ci.yml`) re-runs its own (broader) gate on the
PR, and is the actual required check. A PR cannot merge with a red gate.

## 5. Definition of done

- [ ] Conforms to the frozen contracts / ADRs / invariants (no design drift).
- [ ] New/changed behavior is covered by meaningful tests (positive **and**
      negative cases).
- [ ] `make check` passes locally, **and**, if your change touches a package
      outside the Makefile's 20-package list (§4), CI's broader gate is also
      green before requesting review.
- [ ] Docs updated if the change affects developer workflow or public surface
      — see §7 (Documentation) below for what "updated" means concretely.
- [ ] Conventional-commit messages; no `# type: ignore` / `# noqa` without an
      inline justification.

## 6. Package inventory (current, not Phase-1-foundation-only)

v2 is currently composed of 32 packages, not the 6-package foundation this document once
described. `DEVELOPMENT.md` §3 has the full, current layout table (all 32,
grouped by the four architectural planes) — read it before assuming a package
you're touching doesn't exist yet or is out of scope. **There is no longer a
"later phases, do not implement yet" boundary** — every capability the
Constitution names has shipped. The one real boundary that still applies:
`nexus_core` remains additive and dependency-free of everything above it (§3 of
this document), and no package may cross a dependency direction the
architecture-fitness tests enforce (see `test_guardrails.py` in the relevant
package's test directory, and `docs/benchmarks/quality-gates.md` for a real
example of this boundary catching a violation during development).

## 7. Documentation expectations

A change is not done just because `make check`/CI is green. Update the
relevant documentation in the same PR when your change:

- **Adds or changes a public composition-root function or class** — update the
  package's own docstrings/README (if it has one) and, if the change affects a
  pattern `docs/internals/WALKTHROUGH-v2.md` or an `examples/` script
  demonstrates, update that too. Do not let an example silently drift from the
  API it calls — Phase 4 of this repository's documentation initiative found
  three real bugs precisely because every example was executed, not just
  reviewed; a stale example is worse than no example.
- **Changes measured behavior** (performance, test counts, coverage) —
  `docs/benchmarks/` documents released, evidence-backed measurements only; do
  not hand-edit a number there without re-running the measurement and citing
  it, per `docs/development/DOCUMENTATION_GUIDE.md`'s benchmark rules.
- **Touches an architectural decision** — see §1: do not edit an ADR file to
  reflect a code change. If your change reveals the Constitution and the
  shipped code now disagree, open an issue (or, if you're proposing the
  resolution yourself, a new ADR — see `docs/development/DEVELOPMENT.md` §10 for
  the mechanics, and `adr/ADR-009-runtime-selection-ownership.md` for a real,
  precedent-setting example of exactly this situation).
- **Adds a new package** — add it to `DEVELOPMENT.md` §3's layout table and to
  the Makefile's `PACKAGES`/`TESTS` variables and `core-ci.yml`'s package lists
  (all three currently must be updated by hand — there is no single source of
  truth that generates them, which is itself a known, disclosed gap, not a
  hidden expectation).

## 8. Pull request process

1. Push your branch and open a PR against `master` with a description that
   states what changed and why (link the issue or the report/ADR that
   motivated it, if any).
2. Core CI (`core-ci.yml`) and, if your change touches `nexus/` (v1), the
   legacy `ci.yml` must both go green. Neither is optional; branch protection
   enforces required checks and — per this repository's own actual practice
   during its `v2.0.0` release — will also block on unresolved automated
   review conversation threads even after the underlying code has changed, so
   resolve or explicitly address every review comment rather than assuming a
   stale thread will auto-clear.
3. Keep commits atomic and Conventional-Commits-formatted (§2) — this
   repository's own release history (see `docs/v2/RC1_PRODUCTIZATION_REPORT.md`
   §1) treats "one isolated, reviewable diff per fix" as a hard discipline, not
   a suggestion; squash-on-merge is not this repository's practice (every past
   merge to `master` is a regular merge commit — see
   `docs/releases/README.md` §"Merge strategy").
4. A maintainer merges once the gate is green and review is resolved. Do not
   merge your own PR unless explicitly authorized to.

## 9. Issue reporting

Open an issue when: you find a real defect (include the file:line, the exact
command that reproduces it, and — if you have one — the expected vs. actual
behavior); you believe the Constitution and the shipped code disagree (cite
both sides, per `docs/DOCUMENTATION_PHASE5_REPORT.md`'s own "evidence first,
never invent a contradiction" discipline); or requirements are ambiguous,
conflicting, or incomplete. **Never guess, never invent requirements, never
assume business logic** — this rule carries over unchanged from v1's own
`CONTRIBUTING.md` (root) because it's a repository-wide norm, not a v1-specific
one.
