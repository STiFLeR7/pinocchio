# `docs/runtime/` — As-Built Engineering Documentation

**This is not a duplicate of `docs/v2/`.** `docs/v2/` holds the *frozen target architecture* — written
before implementation began, and preserved as the design record. `docs/runtime/` holds the *as-built
engineering record* for the packages that implement that design: per-subsystem module layouts, real test
counts and coverage, decision logs made while building, and lessons learned. Every document in this tree
either states directly, or is written in the style of, the convention `docs/runtime/recovery/RECOVERY_ENGINE.md`
sets out explicitly: it "conforms to the frozen architecture in `docs/v2/...`... these are engineering
documents, not architecture."

## Why this is a separate tree, not a section of `docs/v2/`

Mixing "what we designed before writing any code" with "what actually shipped, and what we learned
building it" would blur a distinction the platform's own documentation practice depends on: `docs/v2/`
must stay a stable reference you can cite the way you'd cite a contract, while `docs/runtime/` is expected
to accumulate implementation detail, real numbers, and retrospective notes as each subsystem is built.
Some `docs/runtime/` files are also cited **directly from production code** — e.g. `nexus_recovery/vocabulary.py`
references `docs/runtime/recovery/RECOVERY_DECISIONS.md`, and `nexus_validation/vocabulary.py` references
`docs/runtime/validation/VALIDATION_RULES.md` — so this tree is load-bearing documentation, not an
archive.

## How to read it

Each subfolder covers one subsystem (or, for `assessment/`, one due-diligence question) and generally
contains an overview/pipeline doc, a decisions/rules doc, and a `LESSONS_LEARNED.md`. Start with the
overview doc for the subsystem you care about; the `docs/v2/` doc it conforms to is stated in its opening
lines.

| Subfolder | Subsystem | Conforms to (`docs/v2/`) | Start here |
|---|---|---|---|
| `recovery/` | `nexus_recovery` — deterministic governed continuation after failure | `19_RECOVERY.md` | `RECOVERY_ENGINE.md` |
| `validation/` | `nexus_validation` — evidence-driven judgment of execution outcomes | `14_VALIDATION.md` | `VALIDATION_ENGINE.md` |
| `knowledge/` | `nexus_knowledge` — durable operational memory | `knowledge/01_KNOWLEDGE_ENGINE.md` | `KNOWLEDGE_ENGINE.md` |
| `reflection/` | `nexus_reflection` — analytical layer over completed history | `26_REFLECTION.md` | `REFLECTION_ENGINE.md` |
| `workflows/` | `nexus_workflows` — the fused Goal→Knowledge pipeline (the Spine) | `01_ARCHITECTURE.md`, `18_EXECUTION_GRAPH.md` | `WORKFLOW_PIPELINE.md` |
| `research/` | `nexus_research` — autonomous research workflow (a platform consumer) | n/a (Capability Program 3, not a core capability layer) | `RESEARCH_WORKFLOW.md` |
| `briefings/` | `nexus_briefings` — operational briefings (a platform consumer) | n/a (Product Program 1) | `BRIEFING_PIPELINE.md` |
| `operator/` | `nexus_operator` — the operator session experience (a platform consumer) | n/a (Productization Program 1) | `OPERATOR_EXPERIENCE.md` |
| `adapters/` | `nexus_runtime_adapters` and the provider adapters (`CLAUDE.md`, `GEMINI.md`, `SHELL.md`) | `runtime/03_RUNTIME_ADAPTERS.md` | `ADAPTER_REGISTRY.md` |
| `implementation/` | `nexus_execution` — the Execution Engine itself | `08_EXECUTION.md`, `runtime/01_RUNTIME_MANAGER.md` | `EXECUTION_FLOW.md` |
| `assessment/` | Architectural due-diligence: could OmniRoute become a first-class Runtime Adapter? | `runtime/03_RUNTIME_ADAPTERS.md` (evaluated against, not implementing) | `assessment/README.md` |

Every subfolder except `assessment/` also has a `LESSONS_LEARNED.md` — read these when you want to know
*why* something was built the way it was, not just what was built.

## Relationship to other documentation

- **`docs/v2/`** — the frozen target architecture. If `docs/runtime/` and `docs/v2/` ever appear to
  disagree, `docs/v2/` is authoritative for *design intent*; `docs/runtime/` is authoritative for *what
  the code actually does today*. A disagreement between them is a documentation bug worth reporting, not
  a reason to guess which one is "more true."
- **`docs/internals/WALKTHROUGH-v2.md`** — a single, code-first tour across the whole v2 codebase (entry
  point, composition-root pattern, the Spine, event sourcing). Read that first if you're new; come to
  `docs/runtime/` when you need one subsystem's implementation detail it doesn't cover.
- **`docs/v1/`** — unrelated. That tree documents the original, independent v1 codebase (`nexus/`); it has
  no connection to `docs/runtime/` or `docs/v2/`.
- **`docs/architecture/README.md`** — the architecture portal indexing every subsystem (design and
  as-built) from one page. Come here for implementation depth on one subsystem; go there for the map of
  all of them.
