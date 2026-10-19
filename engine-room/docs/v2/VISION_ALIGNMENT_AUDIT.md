# Nexus — Vision Alignment Audit

Status: **Canonical assessment.** Independent, evidence-based audit of Nexus against the *original
vision* (not against current implementation quality). Every conclusion is grounded in `file:line`
evidence read directly from the repository. Prior completion reports (A0/A1/A2, the Architecture
Freeze Review, phase reports) were treated as claims to be verified, not as facts. Where a prior
report overstated integration or capability, this document says so plainly.

Auditor stance: Principal Architect / CTO / independent technical auditor. Evidence wins. Claims do
not. Effort is not rewarded — only implemented, integrated, operational capability is.

Method: full repository walk; four independent parallel sub-audits (Foundation+Harness,
Intelligence layers, Reflection/Knowledge/Planning/Skills, Operations+Integration) each returning
`file:line` evidence; plus direct cross-checks by the auditor (import-boundary greps, entrypoint
tracing, metrics source, runner inspection).

---

## 1. Executive Summary

**How close is Nexus to the original vision?** Roughly **one-third of the way**, and the missing two-
thirds are the *defining* two-thirds. The vision's North Star is a single sentence — *"Nexus should
become the system responsible for understanding work before execution begins"* (`00_VISION.md:252`).
The one capability that has essentially **not been built anywhere** is exactly that: understanding.
There is no intent decomposition, no complexity/cost/duration estimation, no work classification, no
skill/runtime selection by task nature. What has been built — and built well — is a deterministic
execution and orchestration *scaffold*. Nexus today executes; it does not yet think.

**The single most important finding.** Nexus is not one system — it is **three disjoint artifacts**:

1. **v1 `nexus/`** — the *actually running* product: a Discord bot ("Dex") + FastAPI service, DB-
   backed (SQLAlchemy + 5 real Alembic migrations), with real `claude`/`gemini`/`nexus_agent`
   execution runners, a Docker sandbox, an APScheduler scheduler, an outbox, an approvals service,
   and briefings. ~11,739 LOC. Functional but fragile (see Operational Assessment).
2. **v2 `nexus_*`** — a ground-up re-architecture: 20 packages, ~26,700 LOC, ~1,394 passing unit
   tests, internally coherent, deterministic, with a genuinely provider-blind runtime seam.
3. **`docs/v2/`** — 27 numbered design documents (the vision + target architecture).

**v1 and v2 share zero imports in either direction.** `grep -rn "import nexus_" nexus/` → 0 hits;
`grep -rn "from nexus\." nexus_*/` (v1 references) → 0 hits. The sole production entrypoint
(`pyproject.toml:27` → `nexus.__main__:main` → `uvicorn.run("nexus.api:app")`) never touches any
`nexus_*` package. The v2 pipeline is constructed only by v2 packages, integration tests, and the
hand-run `scripts/a0_run.py`. **The elegant v2 architecture is orphaned from the product that
actually runs.**

**What surprised me (positive).** The "runtime executes, Nexus thinks — runtime is an interchangeable
backend" thesis is *real, not aspirational*. `nexus_execution/engine.py:55` drives any runtime
generically and imports no provider (`engine.py:16-18`); `ClaudeRuntimeAdapter`, `GeminiRuntimeAdapter`,
and `ShellRuntimeAdapter` implement one `RuntimeAdapter` Protocol (`nexus_execution/adapter.py:87`);
and a dedicated cross-runtime equivalence suite (`tests/integration/test_cross_runtime.py`, 11/11
passing) proves the *same* governed workflow runs on Claude/Gemini/Shell by adapter substitution
alone. Real subprocess invokers exist for all three. This is the most rigorously realized piece of the
entire codebase — and it delivers the "runtime" half of the thesis. The tragedy is that the "Nexus
thinks" half is the unbuilt half.

**Biggest architectural strengths.**
- Provider-blind runtime seam + interchangeability, CI-proven (above).
- Clean, deterministic, individually well-tested engines with honest, self-documenting scope
  ("no AI," "deterministic," "instrumentation only") — no hidden magic, high testability.
- A real, working in-process Knowledge feedback loop (Reflection → Knowledge → Planning assumptions),
  provably exercised (`tests/integration/test_workflow_pipeline.py:122-127`).

**Biggest missing capabilities.**
- **Executive Intelligence / Intent Resolution (Layer 4)** — the strategic-reasoning layer — is
  essentially **unbuilt**. Its only "estimation" is `len()` + `sum()` (`nexus_planning/plan_builder.py:68-71`).
- **Understanding / decomposition.** Planning is a DAG assembler over caller-supplied `WorkItemSpec`s;
  it never derives a work breakdown from intent (`nexus_planning/decomposition.py:26-30` returns the
  request unchanged).
- **Production integration.** No goal can flow end-to-end through v2 in production today.
- **Durability & operational memory.** All v2 state is in-memory dicts; a restart erases everything
  "learned." Operational metrics (cost, utilization, tool usage, skill performance, success/recovery
  rate, bottlenecks) are not computed anywhere.

**Top three risks.**
1. **Two-system divergence (Critical).** Every day v2 grows while disconnected from v1 increases the
   eventual migration cost and the risk that v2 remains a permanently-unshipped prototype.
2. **Reasoning debt masquerading as completeness (High).** 1,394 green tests and "10 engines" create a
   sense of completeness; but the layers are deterministic scaffolds and the reasoning core is absent.
   Metrics of *effort/coverage* hide the gap in *capability*.
3. **Non-durable learning (High).** The learning loop that does exist is in-process only and never
   fires on the common single-task path — so the "Adaptive Operations" stage is not real yet.

**Overall recommendation.** Stop widening. Do two things, in order: (a) **connect one real vertical to
production** (bridge v2's runtime/governance into the running v1 surface, or vice-versa), and
(b) **build the first genuine reasoning capability** (Intent Resolution: decompose free-text intent
into work items). The architecture is sound enough to freeze *provisionally*; the vision is not yet
achieved because its defining capability — understanding work — has not been started, and nothing v2
built is wired into the product that runs.

---

## 2. Layer-by-Layer Assessment

Scores are deliberately conservative. **Implemented %** = does real logic exist for the layer's vision
scope. **Integrated %** = is it wired into a larger working whole (and, decisively, into the *running
product*). **Operational %** = does it do real work on real data in production today. All three differ.

### Layer 0 — Foundation

| Capability | Impl % | Integ % | Oper % | Evidence | Major gap | Quality | Risk | Conf |
|---|---|---|---|---|---|---|---|---|
| Communication | 0 (v2) / 90 (v1) | 0 (v2) | 90 (v1) | `HarnessCategory.COMMUNICATION` enum only, 0 registrations (`nexus_core/registries/interfaces.py:34`); real in v1 `nexus/communication/*` | No v2 impl; enum label only | v1 real | Med | High |
| Memory | 30 (v2) / 90 (v1) | 40 (v2) | 90 (v1) | v2 = in-mem KV/event store (`nexus_infra/repositories.py:30`, `event_store.py:53`); v1 = DB-backed `nexus/memory/*` | v2 "memory" ≠ operational memory; non-durable | Mixed | High | High |
| Scheduler | 0 (v2) / 90 (v1) | 0 (v2) | 90 (v1) | No v2 scheduler anywhere; v1 `nexus/scheduling/scheduler.py:1-40` (APScheduler) | Absent in v2 | v1 real | Low | High |
| Governance | 10 (v2 scope) | — | 80 (v1) | v2 label only (`interfaces.py:35`); real logic one layer up (`nexus_orchestration/approvals.py`) + v1 `nexus/execution/governance.py:32` | Misplaced vs Foundation; label-only in scope | Mixed | Med | High |
| Approvals | 20 (v2 scope) / 90 (v1) | 60 (v2 orch) | 85 (v1) | `nexus_orchestration/approvals.py:92-105`; v1 `nexus/approvals/service.py:22` | In-scope = fields only; real code is in Orchestration/v1 | Good | Low | High |
| Execution | 85 | 70 (v2 only) | 5 | `nexus_execution/engine.py:55-152` real generic FSM | Not wired to v1; stub invoker by default | Excellent | High | High |
| Runtime Registry | 75 | 70 (v2 only) | 5 | `nexus_runtime/runtime_registry.py:30-123` | In-memory only; not in prod | Good | Med | High |
| Outbox | 0 (v2) / 85 (v1) | 0 (v2) | 85 (v1) | 0 hits in `nexus_*`; real v1 `nexus/gateway/outbox*` | Absent in v2 | v1 real | Low | High |
| Persistence | 40 (protocols+mem) / 90 (v1) | 40 (v2) | 90 (v1) | `nexus_core/persistence/interfaces.py:1-108` ("Nothing here opens a connection"); Alembic binds only `nexus.database.Base` (`alembic/env.py:14`) | No DB for v2 at all | Protocol-clean | High | High |
| Observability | 70 | 65 (v2 only) | 10 | `nexus_infra/observability.py:21-96` (Null/InMemory sinks) | "builds no dashboards, stores nothing durably" | Honest | Med | High |

### Layer 1 — Harness

| Capability | Impl % | Integ % | Oper % | Evidence | Major gap | Quality | Risk | Conf |
|---|---|---|---|---|---|---|---|---|
| Runtime Harness | 90 | 80 (v2) | 5 | `nexus_execution/adapter.py:87`; 3 adapters; real invokers `nexus_runtime_claude/invoker.py:98`, gemini:99, shell:93; cross-runtime test 11/11 | CLI invokers smoke-only, not CI-proven live; not in prod | **Excellent** | Low | High |
| Channel Harness | 0 | 0 | 0 | 0 hits in v2; not even a `HarnessCategory` member; real in v1 `nexus/communication/channels.py` | Not modeled in v2 taxonomy | v1 real | Med | High |
| Skill Harness | 70 | 70 (v2) | 5 | `nexus_harness/skill_resolver.py`, `harness.py:62-78` | `procedure={}` empty in every caller; no selection | Structural only | Med | High |
| Context Harness | 80 | 75 (v2) | 5 | `nexus_harness/context_resolver.py` + full `nexus_context/*` | Deterministic; not in prod | Good | Low | High |
| Validation Harness | 80 | 75 (v2) | 5 | `nexus_validation/{engine,evaluator,rules,evidence}.py` | In-memory; not in prod | Good | Low | High |
| Knowledge Harness | 80 | 75 (v2) | 5 | `nexus_knowledge/{engine,acceptance,evolution,retrieval}.py` | Flat dict, not graph; non-durable | Good | Med | High |
| Recovery Harness | 80 | 75 (v2) | 5 | `nexus_recovery/{engine,classification,rules}.py:186-205` | Fixed rule table; uncalled by execution | Good | Low | High |

### Layers 2–10 (Intelligence, Reflection, Knowledge, Planning, Operations)

| Layer | Purpose | Impl % | Integ % | Oper % | Evidence | Major gap | Quality | Risk | Conf |
|---|---|---|---|---|---|---|---|---|---|
| 2 Context Engineering | Assemble execution context | 80 | 75 (v2) | 5 | `nexus_context/relevance.py:18-36` fixed weight tables; `freshness.py:35-50` arithmetic; `builder.py:86-98` | Deterministic ranking, "no AI scoring" (by design); not in prod | Good/honest | Low | High |
| 3 Skills | Engineering knowledge, not prompts | 40 | 60 (v2) | 5 | `nexus_core/domain/skill.py:23-63` (4/5 fields; no `success_criteria`); `procedure={}` everywhere | Empty procedures; no selection | Structural | Med | High |
| 4 Executive Intelligence | Classify/estimate/select — **strategic reasoning** | **5** | **0** | **0** | Renamed to "Intent Resolution (deprecated alias)" (`01_ARCHITECTURE.md:5-8`); no service; `complexity_estimates = {count, sum}` (`nexus_planning/plan_builder.py:68-71`) | **The reasoning core — unbuilt** | Absent | **Critical** | High |
| 5 Orchestration Intelligence | Decision engine (parallel/suspend/delegate/escalate/merge/checkpoint) | 45 | 70 (v2) | 5 | `nexus_orchestration/queue.py:130-165` (Kahn sort); `dependency_tracker.py:59-100`; `strategy_assigner.py:54-63` | delegate/merge absent entirely; suspend/checkpoint pass-through; retry/escalate live in uncalled `nexus_recovery` | Partial | High | High |
| 6 Execution Intelligence / Supervision | prepare→execute→observe→validate→recover→finalize | 50 | 60 (v2) | 5 | `nexus_execution/engine.py:71-347` real FSM | validate/recover excluded from engine, split across packages it never calls | Partial | Med | High |
| 7 Reflection | Why/root-cause/patterns/recommendations | 60 | 70 (v2) | 5 | `nexus_reflection/analyzers.py:3-6,356-365` (counting/grouping); `patterns.py:56-59` (≥2) | No root-cause (explicitly); ≥2 episodes; no cross-run persistence | Honest agg. | High | High |
| 8 Knowledge | Operational **graph**, not vector search | 55 | 70 (v2) | 5 | `nexus_knowledge/retrieval.py:52-73` linear scan; `relationships` never traversed (`nexus_core/domain/knowledge.py:64-65`) | Flat dict, not a graph; non-durable | Partial | High | High |
| 9 Planning | Intent→…→Execution Graph | 65 | 70 (v2) | 5 | `nexus_planning/planner.py:76-137`; `decomposition.py:26-30` (identity) | Never decomposes intent; caller supplies specs | Good assembler | High | High |
| 10 Operations | Cost/health/utilization/failures/rates/latency/… | 25 (v1) | 30 (v1) | 20 (v1) | `nexus/core/metrics.py:26-83`; `nexus/intelligence/briefing.py:428-490` | cost/utilization/tool-usage/skill-perf/success-rate/recovery-rate/bottleneck **absent everywhere** | Fragmentary | High | High |

---

## 3. Capability Matrix

Status ∈ {NOT STARTED, DESIGNED, PARTIAL, IMPLEMENTED, INTEGRATED, VALIDATED, PRODUCTION READY}.
"Integrated" here means **into the running product**, which is why so few reach it: v2's rich internal
integration does not count as product integration.

| Capability | Designed | Implemented | Integrated (product) | Operational | Prod-Ready | Verified | Owner | Blocking issue | Evidence | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| Interchangeable runtime backend | ✅ | ✅ | ❌ | ❌ | ❌ | ✅ tests | v2 | not wired to v1 | `test_cross_runtime.py` 11/11; `adapter.py:87` | **VALIDATED** (isolated) |
| Real Claude subprocess execution | ✅ | ✅ | ❌ | ⚠️ demo | ❌ | ⚠️ smoke | v2 | only via `scripts/a0_run.py` | `nexus_runtime_claude/invoker.py:98` | PARTIAL |
| Deterministic Context assembly | ✅ | ✅ | ❌ | ❌ | ❌ | ✅ | v2 | not in prod | `nexus_context/relevance.py:18` | IMPLEMENTED |
| Intent → work breakdown (decomposition) | ✅ | ❌ | ❌ | ❌ | ❌ | — | — | identity function | `decomposition.py:26-30` | DESIGNED |
| Complexity/duration/cost estimation | ✅ | ❌ | ❌ | ❌ | ❌ | — | — | `len()`+`sum()` only | `plan_builder.py:68-71` | NOT STARTED |
| Intent classification (domain/priority) | ✅ | ❌ | ❌ | ❌ | ❌ | — | — | no service; fields unset | `nexus_core/domain/intent.py:55-58` | DESIGNED |
| Skill selection (choose among skills) | ✅ | ❌ | ❌ | ❌ | ❌ | — | — | caller hardcodes one skill | `skill_resolver.py:41-51` | NOT STARTED |
| Runtime selection by task nature | ✅ | ⚠️ | ❌ | ❌ | ❌ | ✅ | v2 | capability-match only, not "by nature" | `nexus_runtime_adapters/selection.py:1-9` | PARTIAL |
| Execution graph (DAG) build + cycle check | ✅ | ✅ | ❌ | ❌ | ❌ | ✅ | v2 | over supplied specs | `execution_graph_builder.py:39-97` | IMPLEMENTED |
| Orchestration: parallel/sequential | ✅ | ✅ | ❌ | ❌ | ❌ | ✅ | v2 | rule-derived, not judged | `strategy_assigner.py:54-63` | IMPLEMENTED |
| Orchestration: suspend/resume | ✅ | ⚠️ | ❌ | ❌ | ❌ | — | — | pass-through input | `requests.py` paused_nodes | DESIGNED |
| Orchestration: delegate / merge | ✅ | ❌ | ❌ | ❌ | ❌ | — | — | absent from codebase | grep → 0 | NOT STARTED |
| Orchestration: escalate/retry | ✅ | ✅ | ❌ | ❌ | ❌ | ✅ | v2 | in `nexus_recovery`, uncalled by orch | `nexus_recovery/rules.py:186-205` | IMPLEMENTED (misplaced) |
| Execution supervision FSM | ✅ | ✅ | ❌ | ❌ | ❌ | ✅ | v2 | validate/recover excluded | `engine.py:71-347` | IMPLEMENTED |
| Independent validation (evidence) | ✅ | ✅ | ❌ | ❌ | ❌ | ✅ | v2 | not in prod | `nexus_validation/engine.py` | IMPLEMENTED |
| Recovery decisions | ✅ | ✅ | ❌ | ❌ | ❌ | ✅ | v2 | fixed rule table | `nexus_recovery/classification.py:25-40` | IMPLEMENTED |
| Reflection (patterns/recommendations) | ✅ | ✅ | ❌ | ❌ | ❌ | ✅ | v2 | counting, not root-cause | `analyzers.py:356-365` | IMPLEMENTED |
| Knowledge feedback loop (learn) | ✅ | ✅ | ❌ | ⚠️ in-proc | ❌ | ✅ | v2 | ≥2 episodes; non-durable | `test_workflow_pipeline.py:122-127` | PARTIAL |
| Knowledge operational graph | ✅ | ❌ | ❌ | ❌ | ❌ | — | — | flat dict, no traversal | `retrieval.py:52-73` | DESIGNED |
| Human approval governance | ✅ | ✅ | ⚠️ v1 | ⚠️ v1 | ⚠️ | ✅ | v1+v2 | v2 via demo; v1 real Discord | `nexus/approvals/service.py:22`; `human_approval.py` | INTEGRATED (v1) |
| Repository Intelligence (profile) | ✅ | ✅ | ❌ | ⚠️ demo | ❌ | ✅ | v2 | grounding only; not in prod | `nexus_workflows/repo_profile.py` | IMPLEMENTED |
| Operational metrics (cost/util/etc.) | ✅ | ❌ | ❌ | ❌ | ❌ | — | v1 | not computed anywhere | grep cost/utilization → 0 | NOT STARTED |
| Operational metrics (latency/failures) | ✅ | ⚠️ | ⚠️ v1 | ⚠️ v1 | ❌ | ⚠️ | v1 | in-mem, resets to 0.0 | `nexus/core/metrics.py:26-83` | PARTIAL |
| Durable persistence (v2) | ✅ | ❌ | ❌ | ❌ | ❌ | — | — | Alembic binds v1 only | `alembic/env.py:14` | DESIGNED |
| Scheduler (v2) | ✅ | ❌ | ❌ | ❌ | ❌ | — | v1 | v1 only | `nexus/scheduling/scheduler.py` | NOT STARTED (v2) |
| End-to-end goal → prod through v2 | ✅ | ❌ | ❌ | ❌ | ❌ | — | — | no entrypoint calls v2 | `nexus/api.py` imports | NOT STARTED |

---

## 4. Repository Walkthrough

**What exists.** Three strata in one repo:

- **v1 `nexus/` (11,739 LOC, running).** `api.py` (FastAPI), `communication/{discord,chat,email}`,
  `scheduling/{scheduler,orchestrator,jobs}`, `execution/{runners,sandbox,governance,service}`,
  `approvals/service.py`, `memory/{manager,models,service}`, `gateway/outbox*`, `intelligence/
  {briefing,openrouter,planner}`, `core/{metrics,health,types}`. DB-backed (SQLAlchemy async), 5
  Alembic migrations. This is the product.
- **v2 `nexus_*` (20 packages, ~26.7k LOC, ~1,394 unit tests).** Dependency direction (clean, acyclic):
  `nexus_core` (contracts/domain/registries/persistence protocols) ← everything;
  `nexus_infra` (in-memory event store/repos/observability/clock) ← engines;
  `nexus_context`, `nexus_planning`, `nexus_orchestration`, `nexus_harness`, `nexus_execution`,
  `nexus_runtime` + `nexus_runtime_{claude,gemini,shell}` + `nexus_runtime_adapters`,
  `nexus_validation`, `nexus_recovery`, `nexus_reflection`, `nexus_knowledge`; composed by
  `nexus_workflows` (`PipelineBuilder`/`WorkflowCoordinator`); consumed by `nexus_operator`,
  `nexus_briefings`, `nexus_research`.
- **`docs/v2/` (27 docs).** Vision + numbered architecture specs + invariants.

**How they interact.** Within v2, cleanly and as designed. `nexus_workflows/pipeline.py:74-99` wires
all ten engines over one shared in-memory `InfrastructureContext` and clock; `WorkflowCoordinator.run()`
(`coordinator.py:103-140`) calls them in fixed order. **Across strata: they do not interact at all.**

**Dependency direction.** v2 is a well-formed DAG rooted at `nexus_core`. v1 is its own DAG rooted at
`nexus.core`/`nexus.database`. The two DAGs are disjoint.

**Missing layers.** Executive Intelligence/Intent Resolution (no service). Channel Harness (not even a
taxonomy member in v2). Scheduler, Communication, Outbox (absent in v2). Durable persistence for v2.

**Architectural seams (good).** The `RuntimeAdapter` Protocol (`nexus_execution/adapter.py:87`) and
`adapter_factory` are the single provider-specific choke point — a genuinely clean seam. The
`PlanningRequest.assumptions` field is a clean grounding seam (Knowledge/Repo profile flow through it).

**Dead ends / unused abstractions.**
- `CoordinationModel.PIPELINE` and `EVENT_DRIVEN` (`nexus_core/contracts/enums.py:83-91`) are never
  produced by `strategy_assigner` — dead enum values.
- `Knowledge.relationships` typed edges (`nexus_core/domain/knowledge.py:64-65`) exist but are never
  traversed — the "operational graph" is unused scaffolding.
- `DecompositionStrategy` Protocol — a seam for a "future intelligent decomposer," unimplemented.
- `HarnessCategory.COMMUNICATION` / `.GOVERNANCE` — enum labels with zero registrations.

**Temporary implementations / stubs.** `StubClaudeInvoker` is the *default* execution path
(`coordinator.py:51-53`, `nexus_runtime_adapters/catalog.py:30-31`) — production-shaped fake output.
`OperatorSession.dashboard` hardcodes `running_workflows=0` by design (`nexus_operator/dashboard.py:8-11`).

**Duplicate responsibilities.** Two runtime systems (v1 `runtime_registry` + runners vs v2
`AdapterRegistry` + adapters), two Claude invocation paths, two approvals implementations
(`nexus/approvals/service.py` vs `nexus_orchestration/approvals.py`), two metrics systems, two
persistence models. v2 is largely a cleaner re-implementation of v1 that has not replaced v1.

---

## 5. Intelligence Assessment

The central question: **does Nexus think, or only execute predefined pipelines?**

**Verdict: it only executes.** Every "decision" found in the audited intelligence layers is a fixed
lookup table, an `if/elif` chain, a graph algorithm, or arithmetic — and multiple modules say so in
their own docstrings ("no AI scoring," "contains no AI," "never on heuristics, never on AI").

| Sub-system | Score | Reasoning or deterministic? | Evidence |
|---|---|---|---|
| Context Engineering | 4/10 | Deterministic weight tables | `relevance.py:18-36`; docstring "no AI scoring" |
| Executive Intelligence | **0.5/10** | Not implemented | `plan_builder.py:68-71` = count+sum; no service |
| Orchestration Intelligence | 4/10 | Graph algorithms + rule branches | `queue.py:130-165`; `strategy_assigner.py:54-63` |
| Execution Intelligence | 5/10 | Deterministic FSM | `engine.py:71-347` |
| Reflection | 5/10 | Counting/grouping, no root-cause | `analyzers.py:3-6` |
| Knowledge | 4/10 | Flat dict + linear scan | `retrieval.py:52-73` |
| Planning | 5/10 | DAG assembler, no decomposition | `decomposition.py:26-30` |

**Where any LLM makes a decision.** Exactly one place, and it is in **v1**, not v2:
`nexus/communication/chat/planner.py:103-158` calls an LLM to pick one of five chat actions — but its
own comments admit the model is unreliable and it is **overridden by deterministic regex** for
governance-sensitive actions (email), and governance flags are hardcoded. No LLM is invoked to
classify work, estimate complexity/cost, select a skill/runtime, or decide coordination/recovery
anywhere in `nexus_context/planning/orchestration/execution/recovery/harness/validation`.

**Conclusion.** The determinism is largely *deliberate* (testability-first, invariants demand it) —
which is defensible engineering. But it means the vision's higher-order reasoning ("understanding over
automation," "reason about capabilities," "understand work before execution") has **not been started**.
Nexus is a deterministic pipeline executor with a reasoning-shaped hole where its thesis should be.

---

## 6. Operational Assessment — can Nexus run the full loop?

Marking the vision's end-to-end loop. "Built" = real code exists somewhere; the parenthetical states
*where* and whether it is in production.

| Step | Status | Note |
|---|---|---|
| Receive a goal | **Built** | v1 Discord (prod); v2 `OperatorSession.submit` (tests only) |
| Understand repository | **Built** | v2 `repo_profile.py` (demo/tests only, real) |
| Understand architecture | **Partial** | profile detects structure; no architectural reasoning |
| Plan work | **Partial** | assembles DAG from **supplied** specs; does not decompose intent |
| Assemble context | **Built** | v2 `nexus_context` (deterministic; not in prod) |
| Choose skills | **Missing** | no selection; caller hardcodes one skill (`procedure={}`) |
| Choose runtime | **Partial** | capability-match funnel, not "by task nature"; v1 prod = `task.runtime_id or "gemini"` hardcode |
| Request approvals | **Built** | v1 Discord (real, prod); v2 governed gate (demo) |
| Execute safely | **Partial** | v2 real subprocess exists but stub-by-default & not in prod; v1 runs real in prod |
| Validate independently | **Built** | v2 `nexus_validation` (not in prod) |
| Recover | **Built** | v2 `nexus_recovery` rule table (not called by execution engine) |
| Reflect | **Built** | v2 aggregation (single-episode → nothing) |
| Learn | **Partial** | in-process only; ≥2 episodes; non-durable |
| Improve future executions | **Partial** | Knowledge → assumptions text only; never changes plan structure |
| Report back | **Built** | v1 briefings (prod, but metrics read 0.0); v2 briefings (tests) |

**Production reality of v1 (the running loop).** Observed live evidence (Discord transcript) plus code
confirms the running product is fragile: a task "tell me a joke" failed with *"Tool 'generic_command'
not found"*; "send me a mail" was refused (email intent handling gap, since hardened per commit
`b87e022`); the morning briefing showed **every** performance metric as `Avg 0.0ms | Count 0`. The
last is explained in code: `get_metrics_summary` reads a **process-global in-memory deque**
(`nexus/core/metrics.py:65-82`) that is never restored from the DB, so any restart (or a worker that
hasn't executed since boot) zeroes all metrics simultaneously — exactly as observed. Several declared
metrics (`discord_latency_ms`, `smtp_latency_ms`) have **no call site that records them** at all.

**Can a goal flow end-to-end through v2 in production today? No.** No service, bot handler, scheduler
job, or API route constructs a `WorkflowCoordinator`/`OperatorSession`/`BriefingCoordinator`. The only
path reaching a real Claude subprocess in v2 is `nexus_workflows/a0.py`, run by a human via
`python -m scripts.a0_run` against a throwaway repo copy — self-documented as having "nothing upstream"
importing it.

---

## 7. Original Vision Alignment

| Vision statement | Verdict | Why |
|---|---|---|
| "Runtime executes. Nexus thinks." | **Partially** | Runtime-executes is real & interchangeable; Nexus-thinks is unbuilt |
| "Runtime should become an interchangeable execution backend" | **Achieved** | `adapter.py:87`, 3 adapters, `test_cross_runtime.py` 11/11 |
| "The intelligence must live inside Nexus" | **Not achieved** | No reasoning in v2; the one LLM decision is v1 chat, regex-overridden |
| "Nexus constructs execution context before execution" | **Achieved (deterministically)** | `nexus_context/*` — but rule-based, not "engineered intelligence," and not in prod |
| Context pipeline: repo→architecture→files→commits→issues→ADRs→prev-exec→conventions→prefs→tools | **Partially** | repo/conventions/structure via `repo_profile`; commits/issues/ADRs/prev-executions not assembled |
| "Skills represent engineering knowledge. Not prompts." | **Not achieved** | `procedure={}` empty in every caller; structural placeholder |
| Skill contains context/artifacts/validation/success/recovery | **Partially** | 4/5 fields on `Skill`; no `success_criteria`; procedures empty |
| Executive Intelligence: classify/estimate/select/assemble | **Not achieved** | renamed to deprecated alias; no service; count+sum for "complexity" |
| Orchestration: parallel/sequential/retry/suspend/resume/delegate/escalate/checkpoints/merge | **Partially** | parallel/sequential/retry/escalate exist; suspend/resume pass-through; delegate/merge absent |
| Execution supervised lifecycle (prepare→…→finalize) | **Partially** | execute/observe/finalize real; validate/recover split out & uncalled by engine |
| Reflection: why/root-cause/patterns/recommendations | **Partially** | patterns/recommendations by counting; explicitly **no** root-cause |
| Knowledge: operational graph, NOT vector search | **Not achieved** | flat dict + linear scan; `relationships` never traversed (also not vector — just a dict) |
| Planning: intent→goal→WBS→packages→deps→graph | **Partially** | packages→deps→graph real; intent→WBS not (identity decomposition) |
| Operations metrics (cost/health/util/failures/rates/latency/tools/skills/history/bottlenecks) | **Partially** | latency(some)/failures/history/health(binary) real in v1; cost/util/tool/skill/success-rate/recovery-rate/bottleneck absent |
| "Operators remain the source of authority… Human governance final" | **Achieved** | v1 Discord owner-checked approvals; v2 fail-closed gate |
| "Learning should continuously improve future planning" | **Partially** | loop exists in-process; non-durable; single-task path learns nothing; affects assumptions text only |
| North Star: "understand work before execution begins" | **Not achieved** | the defining capability is unbuilt |

---

## 8. Drift Analysis (most important section)

**Did implementation drift? Yes — but not primarily as sloppy code. The drift is structural and
strategic.** Three drift types dominate:

**1. Integration drift — CRITICAL.** The plan (per `MIGRATION_FROM_V1.md` and the phase commits) was
to build v2 engines and migrate the product onto them. Instead, v2 became a **parallel universe**:
20 packages, 1,394 tests, zero imports to/from the running product, no entrypoint, in-memory-only
persistence with Alembic still bound to v1 (`alembic/env.py:14`). *Where:* the entire `nexus_*` tree.
*Why:* building greenfield engines test-first is faster and cleaner than surgically threading them into
a live async DB-backed bot; the migration was perpetually deferred. This is the highest-cost drift
because it compounds — every new v2 line widens the gulf.

**2. Priority / scope drift — MAJOR.** The vision is emphatic that *understanding* is the hard problem
and the point of Nexus ("Execution is no longer the difficult problem. Understanding is."
`00_VISION.md:17-21`). Yet effort went to **breadth of deterministic execution machinery** (ten
engines, a runtime seam, validation/recovery/reflection scaffolds) and **zero** to the reasoning core
(Intent Resolution / Executive Intelligence). The single most important layer has the least code. *Why:*
deterministic engines are testable and satisfy the invariants; reasoning is fuzzy, hard to test, and
was pushed to "later." Understandable, but it means the platform built everything *except* its thesis.

**3. Documentation / narrative drift — MODERATE.** Docstrings and domain models claim capabilities the
code does not deliver: Knowledge is documented as an "operational graph" (`knowledge.py:43,64-65`) but
is a linearly-scanned dict; layers are framed as "intelligence" but are deterministic; the A0/A1/A2
reports and the Freeze Review describe verticals as "architecture-proving" and imply the architecture
is nearly production-ready, without foregrounding that **none of it is wired into the running product**.
The prior reports are not false — the verticals genuinely ran — but they overstate proximity to a
shipped system. This audit corrects that: the A0/A1/A2 successes are *isolated demos*, not product
integration.

**Not significant:** *Architectural* drift is low — the v2 design is internally coherent and faithful
to the numbered specs. The problem is not that the code diverged from the architecture; it is that the
architecture diverged from the *product*, and the *vision's core* was never begun.

**Estimated drift.** From "intended trajectory" (build engines → migrate product → add reasoning):
- Integration axis: **~70% drifted** (should be threaded into product; is fully separate).
- Capability axis: **~40% drifted** (reasoning layer, the priority, is ~0%).
- Documentation axis: **~30% drifted** (claims ahead of code).

**Recoverability.** **High for integration** — the clean `RuntimeAdapter` seam and the fact that v1
already has a working runtime registry mean a bridge is tractable (A1 already demonstrated a v1↔v2
governance bridge). **Moderate for capability** — Intent Resolution is greenfield work, not a rewrite.
**High for documentation** — this report is the correction.

**Classification: MAJOR (not Critical).** It is Major rather than Critical because the architecture is
sound and recoverable, v1 still runs, and the seams to reconnect exist. It is not Minor/Moderate
because the defining capability is unbuilt and the built work is unshipped.

---

## 9. Remaining Roadmap

**Immediate priorities (foundational).**
1. **Pick one production seam and cross it.** Either (a) route one real v1 task type through v2's
   runtime/governance, or (b) call the v2 pipeline from a real scheduler job. Prove one goal flows
   end-to-end through v2 *in the running process*. This directly attacks the Critical drift.
2. **Durability for v2.** Bind at least Knowledge + Reflection patterns to a real store (reuse v1's DB
   or add SQLite behind the existing `Repository` protocol) so learning survives restart.
3. **Fix v1's metrics zeroing** (operational credibility): restore counters from the DB on boot, or
   compute summaries from `ExecutionRecord` rather than a process-global deque; wire the declared-but-
   dead `discord_latency_ms`/`smtp_latency_ms` (or delete them).

**Next milestones (product).**
4. **First real reasoning capability — Intent Resolution.** Decompose free-text intent into
   `WorkItemSpec`s (the seam already exists via `DecompositionStrategy`). This is the vision's core;
   start it. Measure it against hand-authored breakdowns (an A3-style vertical).
5. **Skill content.** Populate `procedure` with real engineering knowledge for 2–3 skills and prove a
   skill actually shapes execution.

**Future milestones (operational).**
6. Real operational metrics: success rate, recovery rate, cost (token accounting), tool usage — none
   exist today. Build from `ExecutionRecord`/event log.
7. Runtime *selection by task nature* (not just capability match).

**Long-term.** Multi-episode durable learning; Knowledge as an actually-traversed graph; the
"Adaptive Operations" and "Operational Ecosystem" stages.

**Sequencing rule:** do not start #4–#7 broadly until #1 (a production seam) exists — otherwise v2
keeps growing as an orphan.

---

## 10. Technical Debt

| Debt | Detail | Rank |
|---|---|---|
| Integration debt | v2 fully disconnected from product; two runtime systems, two approvals, two metrics, two persistence models | **Critical** |
| Architectural debt | Duplicate responsibilities v1↔v2; dead enum values (`PIPELINE`/`EVENT_DRIVEN`); unused `relationships` graph seam | Medium |
| Knowledge debt | "Operational graph" is a flat dict; no traversal; non-durable; single-episode path writes nothing | High |
| Execution debt | Stub invoker is the default path; real subprocess only via hand-run script; validate/recover not called by execution engine | High |
| Operational/Observability debt | cost/utilization/tool/skill/success-rate/recovery-rate/bottleneck absent; v1 metrics reset to 0.0; no dashboards/export | High |
| Governance debt | Approver identity is a string, not verified RBAC (freeze `G-1`); v2 approvals not in prod | Medium |
| Persistence debt | No durable store for v2; Alembic bound to v1 only | High |
| Testing debt | 1,394 unit tests but ~0 exercise the real CLI runtimes end-to-end (smoke-only); no production integration tests for v2 | Medium |
| Reasoning debt | Executive Intelligence/Intent Resolution unbuilt — the vision's core | **Critical** |

---

## 11. Reality Check

**What is Nexus today?**

- **A framework?** Partly — v2 is a well-structured library/framework for deterministic operational
  pipelines. But a framework is used by something; v2 is used only by its own tests.
- **A platform?** No. Nothing runs on it.
- **An orchestration engine?** Yes, in the narrow, literal sense: v2 deterministically orchestrates a
  fixed sequence of engine stages, and v1 has a simpler event-driven scheduler that *does* run. Neither
  is an *intelligent* orchestrator.
- **An AI operating system?** No. There is no persistent operational substrate coordinating work across
  runtimes/tools/knowledge in production; state is in-memory and per-process.
- **An autonomous engineering system?** No. It cannot decompose intent, choose skills, or learn
  durably; humans must hand-author work items and skills; the autonomous loop is a demo.
- **Something else?** **Yes — most accurately: a running, fragile AI task-bot (v1) sitting beside a
  well-engineered, thoroughly-tested, but unshipped architecture prototype (v2), described by an
  ambitious design corpus (docs).** It is an *architecture-in-waiting*, not yet a control plane.

---

## 12. Final Verdict

How much of the original vision has actually been achieved? Percentages below credit the **whole repo**
(v1 + v2), because the vision does not require capabilities to live in a specific package — but they are
weighted by *operational reality in production*, per the audit's rules.

| Dimension | % | Justification |
|---|---|---|
| **Architecture** | **80%** | v2 design is coherent, invariant-driven, cleanly seamed; runtime interchangeability is real and proven. Deductions: Executive Intelligence exists only as a renamed doc; Channel/Scheduler/Outbox unmodeled in v2; "graph" designed but unused. |
| **Implementation** | **50%** | Most v2 engines are real and tested; v1 foundation (scheduler/comm/outbox/approvals/DB) is real and running. But the reasoning layer is ~0%, skills are empty procedures, and half the ops metrics don't exist. |
| **Integration** | **20%** | v2 is richly integrated *internally* but **orphaned from the product** (0 cross-imports, no entrypoint). Credit is for v1's own working integration + the demonstrated A1 v1↔v2 governance bridge. |
| **Operational capability** | **15%** | v1 runs real tasks (fragile: tool gaps, 0.0 metrics, email gaps). v2 runs real work only via a hand-run script against throwaway repos. No production v2 path. |
| **Autonomy** | **12%** | No intent decomposition, no skill/runtime selection by nature, deterministic-only decisions, non-durable narrow learning. Humans supply the intelligence (work items, skills, coordination). |
| **Product readiness** | **20%** | v1 is a partially-working product with visible failures; v2 is not a product. |
| **Production readiness (v2)** | **8%** | Green unit tests, but in-memory only, stub-by-default execution, no entrypoint, no durability, no real ops metrics. |
| **Overall vision achieved** | **~32%** | Strong architecture and a real runtime seam; but the defining capability (understanding work) is unbuilt and nothing v2 built is wired into what runs. |
| **Auditor confidence** | **~90%** | Every figure traces to `file:line` evidence, cross-verified by four independent sub-audits and the auditor's own import/entrypoint/metrics checks. Residual 10%: dynamic runtime behavior and v1 corners not exhaustively executed. |

**One-line verdict.** Nexus has built, to a high standard, everything *except* the thing it exists to
do — and has not connected what it built to the thing that runs. The architecture is sound and
recoverable; the vision is ~one-third achieved. The next unit of work should be a **production seam**,
followed by the **first real reasoning capability (Intent Resolution)** — not more breadth.

---

*This document is the canonical vision-alignment assessment of Nexus v2. It supersedes optimistic
framing in prior completion reports where they conflict on integration or operational status. It
recommends no code changes by itself; it is an audit.*
