# Nexus — A2 Implementation Report (Repository Intelligence)

Status: **Engineering validation — executed, not designed.** The thinnest reusable Repository
Intelligence capability was built and run against **real, unfamiliar repositories**, producing a
deterministic `RepositoryProfile` that downstream **Planning provably consumes**. Additive code only;
**no ADR, contract, invariant, or existing engine modified.** Nothing committed.

**Headline: Repository Intelligence survived real implementation.** Given an arbitrary repo with no
repo-specific configuration, Nexus now determines type, stack, frameworks, package manager, build,
test framework, structure, dependencies, CI, docs, and conventions from **on-disk evidence** —
deterministically — and hands that grounding to Planning and Context Engineering unchanged.

---

## 1. The Repository Profile (real evidence, two repos)

Run with no configuration:

| Dimension | `D:/port` (unfamiliar) | `D:/nexus` (this repo) |
|---|---|---|
| repository_type | **nextjs-web-app** | **python-app (fastapi/pydantic/sqlalchemy/discord.py)** |
| primary language | typescript | python |
| frameworks | Next.js, React | FastAPI, Pydantic, SQLAlchemy, discord.py |
| package manager | npm (`package-lock.json`) | uv (`uv.lock`) |
| build | npm scripts (`build/start/dev`) | make |
| test | (none detected) | pytest · `tests/` · `pytest` |
| CI | none | github-actions (`ci.yml`, `core-ci.yml`) |
| conventions | eslint, tsconfig | ruff, ruff format, mypy |
| docs (ordered) | CLAUDE.md > AGENTS.md > README.md | README.md > contracts > adr |
| evidence | package.json, package-lock.json, CLAUDE/AGENTS/README | pyproject.toml, uv.lock, Makefile, .github/workflows, .pre-commit-config.yaml |

Benchmark queries, evidence-backed:
- *How is it built?* → `D:/port`: "npm scripts; npm run build/start/dev"; `D:/nexus`: "make".
- *Which tests?* → `D:/nexus`: "pytest; tests/; pytest".
- *Docs first?* → `D:/port`: "CLAUDE.md > AGENTS.md > README.md".
- *Where to fix 'approval'?* (`D:/nexus`) → located `blueprint/DECISIONS/ADR-009-approval-expiration.md`,
  `blueprint/architecture/approval-workflow-design.md`, `docs/v2/human_interaction/05_APPROVALS.md` —
  by **file evidence**, not inference.

Determinism: same repo in → identical profile out (asserted). `7 passed` A2 tests; `30 passed`
workflows suite; ruff clean; mypy clean.

---

## 2. Reused architecture

- **A0's `read_repository`** (`nexus_workflows/repo_intelligence.py`) is the file-walk substrate; A2
  layers the profile on top — no rewrite.
- **`RawContextFragment` + Context Engineering** — the profile projects onto WORKSPACE + CONSTRAINT
  fragments via `profile_to_context_fragments`, the exact seam A0 already used.
- **`PlanningRequest.assumptions` → `Plan.assumptions`** — the profile grounds Planning through the
  existing field; `plan_builder` carries it unchanged (proven: `test_planning_consumes_profile_assumptions`).
- Standard library only (`tomllib`, `json`) — no embeddings, no search, no memory, per the A2 rule.

## 3. New code (all reusable; no repo-specific config)

| File | Purpose | LOC |
|---|---|---|
| `nexus_workflows/repo_profile.py` | `RepositoryProfile` + 10 sub-profiles, deterministic detectors, 4 evidence-backed queries, 2 integration seams | ~450 |
| `tests/unit/nexus_workflows/test_a2_repo_profile.py` | 7 deterministic tests (python/node synthetic + real + Planning consumption) | ~150 |

Object model: `RepositoryProfile{ TechnologyStack, BuildProfile, TestProfile, DocumentationProfile,
ProjectStructure, DependencyProfile, CiProfile, ConventionHints, OwnershipHints }` — one canonical,
frozen, deterministic artifact. Queries: `how_is_it_built`, `relevant_tests`, `docs_to_consult`,
`where_to_fix`. Seams: `profile_to_context_fragments`, `profile_to_assumptions`.

## 4. Remaining gaps (honest, evidence-observed)

1. **"Dependency graph" is a dependency *inventory*, not edges.** A2 lists direct + dev dependencies
   from the manifest; it does not build an import/edge graph (deliberately — "lightweight", no RAG).
2. **Package-per-directory Python layouts under-detected.** `D:/nexus` uses `nexus_*` packages (no
   `src/`), so `source_dirs` came back empty. The heuristic knows `src/app/lib/...`, not "every
   top-level dir containing `__init__.py`". Real limitation, not a wrong answer.
3. **Config in sibling files partly missed.** `line_length` reads only `pyproject.toml`; `D:/nexus`
   keeps it in `ruff.toml`, so it returned `None`.
4. **Makefile target extraction is naive** — variable assignments (`COV_MIN`, `PACKAGES`) can appear
   among targets. Cosmetic; does not affect build-system identification.
5. **Framework/manager detection is a known-signal map** — unlisted frameworks are simply absent, not
   guessed (fail-quiet, by design).

None of these blocked the benchmark or required an engine change; each is additive to close later.

## 5. Architectural conflicts

**None.** Repository Intelligence stayed strictly *grounding*: it reads disk and emits one
deterministic profile, then stops — it does not plan, search, normalize, or remember. It consumes no
engine and is consumed only through the existing context-fragment and assumptions seams. No
`ARCHITECTURAL_CONFLICT_*` was produced.

## 6. Production blockers

1. **Layout coverage** — real polyglot/monorepo detection (per-package Python, workspaces, nested
   manifests) beyond the common cases.
2. **No content-level analysis** — the profile is structural; "likely coding conventions" is inferred
   from config files, not from reading source (acceptable for grounding; a limit for deep planning).
3. **Profile not yet a frozen contract** — it is an HI-layer value object; promote when a second
   consumer depends on its shape (mirrors the freeze review's "don't pre-freeze").

---

## Final Verdict

1. **Did Repository Intelligence survive real implementation?** **Yes.** It profiled two real,
   structurally different repositories with zero configuration, deterministically, from evidence, and
   fed Planning without any engine/ADR/contract/invariant change or architectural conflict.

2. **How much repository understanding is now operational?** The **structural** benchmark is largely
   covered: type, language(s), framework(s), package manager, build, test framework, structure,
   dependency inventory, docs, architectural artifacts, CI, entry points, and conventions — all from
   evidence. Not covered: a true dependency-edge graph and content-level convention inference. Call it
   **~70–75% of the benchmark**, all of it grounding.

3. **Which assumptions proved correct?** (a) Manifests + config files are enough to characterize a repo
   deterministically without embeddings/search. (b) The existing `assumptions`/context-fragment seams
   accept grounding with no engine change. (c) Determinism holds (pure disk read, sorted output).

4. **Which assumptions failed?** That a fixed `src/app/lib` heuristic generalizes — Python
   package-per-directory layouts (like `nexus_*`) need a smarter source-dir rule; and that all config
   lives in `pyproject.toml` — sibling files (`ruff.toml`) are missed. Both are detection gaps, not
   design failures.

5. **Does Planning now operate with materially better grounding?** **Yes — demonstrably.** Where
   Planning previously received an empty/among-generic context, it now receives
   `repository-type: nextjs-web-app`, `build-system: npm scripts`, `source-dirs: app, components`,
   `conventions: eslint`, etc., carried verbatim into `Plan.assumptions`. Planning that knows the repo
   is Next.js with npm/eslint can decompose and target work far more correctly than one that does not.

6. **Standalone subsystem, or migrate into Context Engineering / Engineering Intelligence?**
   **Keep it a standalone reusable *capability*, wired as Context Engineering's repository source —
   not its own heavy subsystem, and not inside Planning.** Evidence: its sole output is a deterministic
   profile that is *context*; Context Engineering's job is assembling context, so Repository
   Intelligence is naturally its repository collector (the `profile_to_context_fragments` seam already
   fits). It must **not** live in Planning (Planning consumes grounding, never produces it) and it is
   more than an EI concern (EI *uses* the profile to choose an approach; it doesn't gather it). Promote
   the `RepositoryProfile` to a frozen `nexus_core` contract only when a second engine depends on its
   shape — consistent with the Architecture Freeze Review's "grounding capability, not a pillar" verdict.

7. **What should A3 validate?** **A3 — profile-driven planning correctness on a real bug.** Feed a real
   `where_to_fix` result + the profile into the A0 vertical so a real Claude session is pointed at the
   *right* files with the *right* test command, and verify (independently) that the fix lands in the
   located area and the profile's test command actually validates it. That closes the loop from
   *grounding* → *correct targeted work* → *independent validation* — the last unproven link between
   "understands the repo" and "plans correct work." (Live Discord + remote push, deferred from A1,
   remains a parallel candidate.)

**Recommendation:** Repository Intelligence is confirmed by execution as a deterministic grounding
capability. Continue one vertical at a time (A3: profile-driven targeted fix); wire the profile into
Context Engineering as its repository source; do not expand into search/embeddings/memory.
