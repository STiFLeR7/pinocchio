# P7 Implementation Report — Repository Intelligence (Grounding Layer)

- **Date:** 2026-07-14
- **Program:** P7 (Repository Intelligence) as briefed — the constitutional **Grounding** owner of understanding repositories
- **Governing decisions:** ARCHITECTURE_CONSTITUTION (Grounding plane; grounding "serves facts by reference, never plans/decides/executes" — INV-27; Article IV determinism), ADR-001 (event authority / determinism), ADR-007 (durable log), ADR-008 (shadow-adjudicable). The A2 `repo_profile` prototype is the shape/logic evidence.
- **Rule observed:** implementation only — no redesign, no protocol/contract/invariant/ADR edits, no engine redesign, no commit.

---

## 1. Executive Summary

`nexus_repository` is the constitutional **Repository Intelligence** subsystem — the single owner of *understanding repositories* (INV-02, Grounding plane). Given a repository root it **scans once** and produces **exactly one** immutable, **facts-only** `RepositoryProfile`. It only understands repositories: it never reasons, plans, orchestrates, executes, validates, recovers, reflects, evaluates policy, estimates complexity, chooses runtimes, or classifies engineering work — each proven by an import-level guardrail. The profile contains **no recommendations, no opinions, no strategy, no planning** — only grounded facts, and it is a **pure function of the repository tree** (identical tree → identical profile → identical identity).

The profile covers every listed responsibility as deterministic disk evidence: repository discovery, workspace inventory, project classification, language/framework/dependency detection, build-system/test-framework/CI detection, ADR/contract/invariant discovery, package inventory, **module dependency graph** (Python imports via `ast`), coding-convention extraction, ownership, git snapshot facts, issue inventory (on-disk templates, no remote fetch), repository **health signals** (factual presence indicators only), and an execution-history lookup **seam**.

**It reasons through nothing — it observes.** The scan runs once, the engine records **one** `repository.profiled` fact embedding the profile (INV-17), and replay reconstructs the understanding **without rescanning**. Durability is transparent through P1 (ADR-007). **Engineering Intelligence consumes the profile** as its Repository Understanding grounding input (via `RepositoryProfile.as_facts()`); Repository Intelligence imports **neither EI nor Planning** — the dependency direction stays constitutional (grounding depends only on the foundation).

**No engine was rewritten; no protocol, contract, or invariant was changed.**
- **New package — `nexus_repository/`** (11 modules): `profile` (the facts-only value objects), `scanner` (the standalone file-walk), `discovery` (evidence extractors, promoted from the A2 prototype), `graph` (module graph + package inventory), `inventory` (ADR/contract/invariant + issue + git + health), `engine`, `events`, `ids`, `observability`, `persistence`, `composition`, `__init__`.
- **Additive EI integration** (one optional param on `strategize_for_goal`): EI consumes a `repository_profile` as grounding facts, **duck-typed** so EI takes no dependency on `nexus_repository`.
- **Changed — `pyproject.toml`** (added `nexus_repository`).

**Tests** — `tests/unit/nexus_repository/` (5 files + fixtures) + `tests/integration/test_repository_durable.py`.

> **Program-label note (sequencing, not a conflict).** The Engineering Program numbers Repository Intelligence as **P4** (off the minimal thinking-path, parallel band). This task briefs it as **P7**, after the reasoning spine (P4–P6) so EI has a grounding source to consume. Same label/sequencing divergence noted since P4; not a constitutional conflict — Repository Intelligence is a Grounding-plane subsystem the Constitution explicitly defers to its own package, and building it after EI lets EI consume it immediately.

---

## 2. Constitutional Compliance

| Requirement | Status | How |
|---|---|---|
| Repository Intelligence is the **single owner of repository understanding** (INV-02) | ✅ | Only `nexus_repository` produces a `RepositoryProfile`; guardrail proves no other package constructs one. |
| It **only understands** — never reasons/plans/executes/validates/recovers/reflects/estimates/chooses-runtimes/evaluates-policy/classifies-engineering-work | ✅ | Import guardrail: imports none of planning/engineering/orchestration/runtime/execution/validation/recovery/reflection/policy/intent/estimation/workflows; references no `EngineeringStrategy`/`PolicyDecision`/`EstimationReport`; no LLM/random. |
| Output is **facts only** — no recommendations, opinions, or strategy | ✅ | Every facet is a raw fact (booleans, counts, names, file paths); `health` is presence signals, not a grade; `as_facts()` carries no opinion/strategy keys (guardrail). |
| Project classification is a **fact**, not engineering-work classification | ✅ | `repository_type` is a project-kind fact (e.g. `python-library`); engineering-work classification remains EI's (guardrail: RI references no EI types). |
| **Deterministic** — pure function of the tree | ✅ | Sorted iteration, no clock/randomness in the scan; content-addressed identity over the repository facts. Proven by repeated-scan equality. |
| **EI consumes RepositoryProfile** (never inspects repos itself) | ✅ | `strategize_for_goal(repository_profile=…)` feeds `profile.as_facts()` as Repository Understanding; guardrail proves EI never imports `nexus_repository`, calls `scan_tree`, or uses `os.walk`. |
| **Planning never scans repositories** | ✅ | Guardrail: Planning imports no `nexus_repository`, no `scan_tree`/`os.walk`. |
| **Dependency direction** — RI imports neither EI nor Planning | ✅ | `nexus_repository → {nexus_core, nexus_infra}` only (guardrail). |
| Determinism seam (INV-17) | ✅ | Scan once → one `repository.profiled` fact → replay reconstructs without rescanning. |
| Profile is a subsystem value object, not a new frozen contract (INV-07) | ✅ | `repository_understanding` is a *Proposed* void (no `contracts/repository_understanding.md`); the profile is a `ValueObject` (the estimation/EI/intent pattern) — no contract frozen or edited. |

**Determinism vs. "execution history lookup" (surfaced, not silently reconciled).** The task lists both "execution history lookup" and "identical profiles across repeated scans." Coupling execution history (from the event log) into the profile would make a re-scan differ from the first (breaking idempotency and the durable-append idempotency). Per the Constitution, **Execution History is a *separate* Grounding subsystem** (listed distinctly from Repository Intelligence). So P7 models `execution_history` as a **lookup seam** (`available=False` until that subsystem exists) and keeps it **out of the profile's deterministic identity**. This preserves both determinism and the constitutional ownership boundary — reported here rather than silently folding the log into the scan.

---

## 3. Repository Intelligence Architecture

```
repository root
      │  scan once (read-only, deterministic)
      ▼
  scanner.scan_tree ──► RepositorySnapshot (inventory, languages, file_count, git facts)
      │
      ├─ discovery.*   → technology, dependencies, build, test, docs+ADR, structure, CI, conventions, ownership, repository_type
      ├─ graph.*       → package inventory, module dependency graph (ast imports)
      ├─ inventory.*   → ADR/contract/invariant artifacts, issue inventory, git summary, health signals
      ▼
  RepositoryIntelligence.profile ──► RepositoryProfile (facts only; identity = hash of the facts)
      │  emit once
      ▼
  repository.profiled  (durable, correlated; embeds the profile)
      │  replay forever (no rescan)
      ▼
  RepositoryProfile.model_validate(payload["profile"]) == profile
      │  as_facts()
      ▼
  Engineering Intelligence  (Repository Understanding grounding input)
```

- **Promotion, not reinvention.** The evidence extractors in `discovery.py` are the A2 `repo_profile` prototype's logic **unchanged**, re-expressed as pydantic `ValueObject`s (so the profile serializes and replays) and wrapped in the constitutional engine convention (events/ids/observability/persistence/composition). The file-walk was **reimplemented standalone** in `scanner.py` rather than reusing the prototype's `nexus_workflows` walker — importing `nexus_workflows` would pull downstream engines in and break the dependency direction.

---

## 4. Discovery Pipeline

| Responsibility | Source of truth (deterministic) |
|---|---|
| repository discovery / workspace inventory | `scan_tree` — sorted top-level entries, dirs, file count |
| project classification | `repository_type` from language + frameworks + structure (a fact) |
| language detection | file extensions → languages (sorted) |
| framework / dependency discovery | `pyproject.toml` / `package.json` manifests (parsed, not executed) |
| build / test / CI detection | Makefile / build-backend / scripts; pytest/jest/vitest/playwright; `.github/workflows`, gitlab, azure, circleci |
| ADR / contract / invariant discovery | `adr/`, `contracts/`, `*INVARIANT*.md` file enumeration (sorted, bounded) |
| package inventory / module dependency graph | dirs with `__init__.py`; intra-repo `import` edges via `ast` |
| coding convention extraction | ruff/black/eslint/prettier/mypy, line-length, editorconfig, pre-commit |
| git history summarization | `.git/HEAD` → branch + head commit (snapshot facts; no history walk, no shelling out) |
| issue inventory | `.github/ISSUE_TEMPLATE` (on-disk only; no remote fetch) |
| execution history lookup | seam (empty until the Execution History subsystem exists) |
| repository health signals | presence facts: has_readme/tests/ci/lockfile/license/codeowners + file_count |

Every extractor is a pure function of the tree, appends to a single `evidence` list, and sorts its outputs — so the whole profile is reproducible.

---

## 5. Grounding Model

The `RepositoryProfile` is **directive of nothing** — it answers *what is true about this repository*, never *what to do about it*. `as_facts()` projects it to a flat facts mapping (languages, frameworks, build/test systems, source dirs, packages, ADR/contract/invariant files, CI, health booleans, file count) that Engineering Intelligence consumes as its Repository Understanding input. EI reads these facts to keep its Strategy grounded; Repository Intelligence never reads back what EI decides. This is the Constitution's grounding contract: *serve facts by reference, then stop* (INV-27) — the grounding plane feeds Reason and Contextualize and owns no decision.

---

## 6. Persistence

- **Durable events** (`test_repository_durable.py::test_profile_event_is_durable_and_correlated`): the `repository.profiled` fact survives reopening the SQLite file, correlated (INV-39).
- Rides P1 unchanged — no `Durable*` repository class; durability is a property of the injected `InfrastructureContext`. Profiles persist through a reused `InMemoryRepository`; over a durable context they ride the durable substrate (ADR-007).
- **Idempotent** (`test_engine.py::test_repeated_scan_is_idempotent_in_the_log`): re-scanning an unchanged tree re-emits the same content-addressed fact → a durable-append no-op, not a duplicate.

---

## 7. Replay Validation

- **Replay reconstructs the profile without rescanning** (`test_replay_reconstructs_profile_without_rescanning`): `RepositoryProfile.model_validate(event.payload["profile"])` equals the original.
- **Restart reconstruction is identical** (`test_restart_reconstruction_is_identical`): a fresh engine over the reopened durable file reproduces the value-equal profile identity.
- **Identical profiles across repeated scans** (`test_profile.py::test_profile_is_deterministic_across_repeated_scans`) and **deterministic IDs** (content hash of the facts).
- **Serialized round-trip** (`test_profile_reconstructs_from_serialized_form`) and **deterministic empty profile** for a missing repository.

---

## 8. Integration Points

- **Consumes:** a repository root path + the P1 `InfrastructureContext`. `build_repository(infrastructure)` is the single DI seam. Imports only `nexus_core` + `nexus_infra`.
- **Produces:** one `RepositoryProfile` per scan; a `repository.profiled` durable event.
- **Engineering Intelligence** consumes the profile via `strategize_for_goal(repository_profile=…)` → `profile.as_facts()` as Repository Understanding. **Intent Resolution** may reference the profile facts (it takes no dependency on it). **Planning** consumes repository grounding only *indirectly* through the `EngineeringStrategy` (P6) — it never scans.
- **Dependency direction:** `nexus_repository → {nexus_core, nexus_infra}`; EI/Intent/Planning → (optionally) the profile *value*, never the scanner. Repository Intelligence imports no engine — guardrail-proven.

---

## 9. Risks

| Risk | Severity | Note / mitigation |
|---|---|---|
| Execution-history lookup is a stub | Low (by design) | Execution History is a separate Grounding subsystem (Constitution); coupling it in would break determinism/idempotency. The seam is present and empty until that subsystem exists. Documented in §2. |
| Git summary is a snapshot, not full history | Low | Deep history walk is non-deterministic over time and would require reimplementing git object traversal; P7 records deterministic `.git/HEAD` facts (branch + commit). Deeper summarization defers to an Execution/History subsystem. |
| Scan cost on very large repos | Low | The walk skips vendored/generated dirs and is bounded (`max_files`); `log()`-style truncation is bounded and sorted. No benchmark harness (out of scope); the scan is a single indexed walk. |
| Language coverage is manifest-based | Low | Framework/dependency detection is evidence-based on well-known manifests (Python/JS today); additive — new ecosystems extend the tables without a schema change. |
| Profile carries a timestamp → equality needs a fixed clock | Low | The facts and identity are timestamp-free and deterministic; only the bundle stamps recording time (INV-17, injected). Tests compare fixed-clock profiles / identities. |

**No constitutional conflict was discovered.** The one place evidence pressed against the brief — "execution history lookup" vs. "identical profiles across repeated scans" — resolved to keeping execution history a separate-subsystem lookup seam outside the deterministic identity (§2), not a change to any architecture.

---

## 10. Remaining Work Before P8

Repository grounding is now durable and consumed by EI. Outstanding, none blocking:

1. **Execution History subsystem:** the separate Grounding producer the `execution_history` seam reads from (prior execution outcomes for a repo) — a later program.
2. **Richer EI use of the facts:** EI currently consumes the profile as grounding (raising confidence via completeness and entering the decision identity); deepening the reasoner's use of specific facts (ADR presence → rigor, framework → approach) is an EI-reasoning enhancement, not a grounding change.
3. **Contextualize integration:** the profile also projects cleanly onto Context Engineering fragments (the prototype had that seam); wiring Context Engineering to consume it is a Contextualize-side step.
4. **Freeze `repository_understanding` contract** if/when a second consumer needs the shape (INV-07 discipline) — deferred, not precluded; the profile is a clean value object a freeze can adopt.

**Verdict:** P7 is functionally complete. Repository Intelligence is the single owner of repository understanding; it produces one immutable, facts-only `RepositoryProfile` that is deterministic, durable, and replayable without rescanning; Engineering Intelligence consumes it instead of inspecting repositories itself; Planning never scans; and no engine, protocol, contract, or invariant was changed. **No commit was made.**

---

## Validation summary

| Suite | Result |
|---|---|
| `nexus_repository` unit + durable integration | **24 passed** |
| Full v2 `nexus_*` unit + integration sweep (incl. additive EI integration) | **2593 passed**, 1 skipped |
| Lint (`ruff`) on new package + tests + EI change | **clean** |

> Run with `--noconftest`: the repo-root `conftest.py` imports the v1 app (requires `discord`, absent here) — a pre-existing environment condition; the v1-app tests need the v1 `db_session`/settings fixtures and are outside the v2 sweep, exactly as in the P1–P6 reports.
