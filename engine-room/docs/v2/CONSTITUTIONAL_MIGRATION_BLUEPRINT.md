# Nexus — Constitutional Migration Blueprint

Status: **Migration strategy.** The `ARCHITECTURE_CONSTITUTION.md` is law. This document does not design
new architecture — it describes **how today's repository becomes the constitutional architecture with
minimum risk**, additively, one releasable stage at a time, with **no big-bang rewrite**.

Verification basis: current-state facts below were re-derived directly from source (package listings,
import greps, entrypoint tracing, v1 subpackage inspection) during this analysis, not taken from prior
implementation reports. Where a prior report is contradicted by source, source wins and it is noted.

Rules honored: no implementation, no code, no new architecture, additive migration preferred, rewrites
avoided, every stage keeps the repository compiling, tested, and releasable.

---

## Executive Summary

**The migration is a convergence, not a construction.** The three prior assessments framed the
constitutional capabilities (durable Memory, Policy Engine, Actuation, Human Interaction channel,
Operations) as "voids." Direct inspection of `nexus/` corrects that in the way that most changes the
migration plan: **v1 already contains real, running, DB-backed implementations of exactly those
capabilities.**

| Constitutional capability the audit called a "void" | Where it already exists, working, in v1 |
|---|---|
| Durable Memory / Persistence (Foundation) | `nexus/memory/{manager,models,service,task_service}.py` (SQLAlchemy async + 5 Alembic migrations) |
| Policy Engine (Govern) | `nexus/memory/policy_service.py` + `nexus/core/policy_defaults.py` |
| Approvals surface (Govern) | `nexus/approvals/service.py` + `nexus/communication/discord/` (real owner-checked Discord) |
| Actuation substrate (Act) | `nexus/execution/sandbox/` (Docker/subprocess) + `execution/governance.py` |
| Outbox / Scheduler (Foundation) | `nexus/gateway/{outbox,communication_outbox}.py` · `nexus/scheduling/{scheduler,jobs}.py` |
| Operations metrics (Operate) | `nexus/core/metrics.py` + `nexus/intelligence/briefing.py` |
| Communication Harness (Foundation) | `nexus/communication/{discord,email,chat,channels}.py` |

Meanwhile **v2 (`nexus_*`) holds the constitutional reasoning/execution spine** — Context, Plan,
Coordinate, Execute, Validate, Recover, Reflect, Learn, and the genuinely interchangeable Runtime — but
**orphaned from the running product and entirely in-memory** (verified: zero imports between `nexus/` and
`nexus_*` in either direction; sole entrypoint `nexus.__main__:main` never touches v2).

So the repository already contains **both halves of the Constitution**, split across two disconnected
strata: **v2 is the "Nexus thinks" half; v1 is the durable "runtime executes" + governance + persistence
half.** The migration is to **converge them** — wrap v1's durable Foundation/Governance behind
constitutional seams, promote three v2 prototypes into their own capability packages, build the two
genuinely-missing reasoning heads (Intent Resolution, Engineering Intelligence), and route production
traffic from v1's ad-hoc decisions onto the constitutional capabilities **one strangled decision at a
time, behind flags, in shadow mode first.**

**The single strategy: Strangler Fig, decision by decision.** v1 stays the running product throughout.
Each weak v1 decision (e.g. `runtime = task.runtime_id or "gemini"` in `nexus/scheduling/orchestrator.py`;
the regex-overridden LLM in `nexus/communication/chat/planner.py`) is replaced by routing that one
decision through the constitutional owner — first computed in **shadow mode** (logged, not acted on),
then flipped behind a feature flag. Nothing is rewritten; v1 logic is *strangled* as each constitutional
owner proves itself.

**Highest-leverage first moves (ranked in §7):** (1) bind v2 to a **durable substrate** by reusing v1's
DB behind v2's existing `Repository` protocol; (2) extract the **Policy Engine** from v1's policy
service; (3) open the **first production seam** (runtime selection). These three unblock nearly
everything else and each is additive and releasable.

**Bottom line:** the constitution is reachable without a rewrite. Roughly **60% of the constitutional
substrate already exists** (split across v1 durable + v2 spine); the migration is wiring, promotion of
three prototypes, two new reasoning packages, and a disciplined strangler cutover — sequenced so the repo
is releasable at every stage.

---

## 1. Repository Classification

Every package classified **Constitutional** (it *is* the target, keep), **Transitional** (keep now, will
be reshaped/absorbed), **Legacy** (running product; wrap/migrate, do not delete), or **Deprecated** (a
duplicate/obsolete concept to retire on a schedule). Impl caveats noted separately from architectural
verdict.

### v2 `nexus_*` — the constitutional spine (mostly Constitutional)

| Package | Class | Why |
|---|---|---|
| `nexus_core` | **Constitutional** | Canonical object model + contracts + registries + persistence protocols (INV-07). The constitution's Object Model home. |
| `nexus_infra` | **Constitutional (impl transitional)** | Correct substrate role (event log, repos, observability, clock) — but **in-memory only**; must be backed by a durable store (Stage 1). Architecturally right, durability wrong. |
| `nexus_context` | **Constitutional** | Contextualize capability. Deterministic assembly, matches Article. |
| `nexus_planning` | **Constitutional** | Plan capability — and per Constitution absorbs Execution-Strategy/Skill-Selection/Work-Packaging. |
| `nexus_orchestration` | **Constitutional** | Coordinate capability (runtime selection INV-37, pause/resume INV-23). |
| `nexus_harness` | **Constitutional** | Harness category model + Skill/Context/Validation/Recovery/Knowledge resolvers (INV-34/35). |
| `nexus_runtime` | **Constitutional** | Runtime Manager + Registry (INV-36). |
| `nexus_runtime_adapters` | **Constitutional** | Adapter registry/selection/catalog. |
| `nexus_runtime_claude` / `_gemini` / `_shell` | **Constitutional** | Execute backends — the interchangeable Runtime (best-realized part; cross-runtime test 11/11). |
| `nexus_execution` | **Constitutional** | Execute capability (provider-blind FSM). |
| `nexus_validation` | **Constitutional** | Validate (evidence-based, INV-20). |
| `nexus_recovery` | **Constitutional** | Recover (INV-22). |
| `nexus_reflection` | **Constitutional (impl transitional)** | Reflect — correct, but single-episode/no-durable-history limit until Stage 1. |
| `nexus_knowledge` | **Constitutional (impl transitional)** | Learn — correct governance, but flat-dict "graph" + non-durable; needs durability + real traversal. |
| `nexus_workflows` | **Transitional** | Composition root + prototype verticals. `pipeline.py`/`coordinator.py` = the spine runner (reshape); `a0.py`/`a1.py` = demo verticals (fold); `repo_profile.py`+`repo_intelligence.py`/`human_approval.py`/`git_actions.py` = **prototype seeds to promote** (§7). |
| `nexus_operator` | **Transitional** | Operate surface (dashboard/timeline/session) — scaffolding, test-only; re-home into Operations. |
| `nexus_briefings` | **Transitional** | Reporting surface on the stub pipeline; test-only. Re-home into Operations or rebuild on real pipeline. |
| `nexus_research` | **Transitional** | A domain workflow consumer; test-only. Keep as a vertical, re-wire to the real pipeline. |

**No package exists for these constitutional capabilities** (verified absent): `nexus_intent`
(Understand), `nexus_engineering` (Reason/EI), `nexus_repository` (Ground), `nexus_policy` (Govern),
`nexus_human_interaction`, `nexus_actuation` (Act), `nexus_operations`, durable `nexus_memory`. These are
the **build/promote targets**.

### v1 `nexus/` — the running product (Legacy: wrap/migrate, never delete wholesale)

| Subpackage | Class | Why |
|---|---|---|
| `nexus/memory/` | **Legacy → migrate (asset)** | Durable SQLAlchemy store — the substrate v2 lacks. Highest-value legacy asset. |
| `nexus/approvals/` + `nexus/communication/discord/` | **Legacy → wrap** | Real owner-checked approvals; becomes a Human-Interaction Channel Adapter. |
| `nexus/communication/{email,chat,channels}` | **Legacy → wrap** | Communication Harnesses (transport). |
| `nexus/execution/sandbox/` | **Legacy → wrap** | Actuation substrate seed (Docker/subprocess isolation). |
| `nexus/execution/runners/` | **Legacy → replace (gradually)** | v1's own runtime runners; overlaps v2's adapters (duplicate). Strangle onto v2 Runtime. |
| `nexus/execution/governance.py` | **Legacy → migrate** | Governance-manager logic → Policy Engine. |
| `nexus/scheduling/` | **Legacy → keep + wrap** | Scheduler (Foundation). `orchestrator.py` = ad-hoc; strangle its decisions. |
| `nexus/gateway/` (outbox) | **Legacy → keep** | Real outbox (Foundation). |
| `nexus/memory/policy_service.py` + `nexus/core/policy_defaults.py` | **Legacy → migrate (asset)** | Policy Engine seed (INV-28 owner). |
| `nexus/intelligence/{briefing,metrics,feed,summary}` | **Legacy → migrate** | Operations seed. |
| `nexus/intelligence/openrouter.py` | **Legacy → wrap** | LLM client → a Runtime capability for the Reason/Understand heads (INV-32). |
| `nexus/intelligence/{research}` + `chat/planner.py` | **Deprecated (behavior) → strangle** | The regex-overridden LLM planner is exactly the ad-hoc "thinking" EI replaces. |
| `nexus/agents/` | **Legacy → replace** | v1 "nexus_agent"/Hermes runner; overlaps v2 runtime. |
| `nexus/api.py`, `nexus/__main__.py` | **Legacy → keep (the host)** | The running host the strangler grows inside; retire last. |

### Deprecated concepts (retire on schedule, never abruptly)

Dual runtime registries · dual approval engines · dual metrics systems · dual persistence models · the
name "Executive Intelligence" · the "12 linear layers" framing · "Supervision layer" (→ Observe) ·
"Communication service"/"Channel Harness" (→ Communication Harness category + HI) · `StubClaudeInvoker`
as a *production* default (keep for tests only).

---

## 2. Constitutional Mapping (every v2 package → capability → Article)

```
nexus_core          → (Object Model / Foundation)         → Articles VI, VIII
nexus_infra         → Foundation (Event Log, Observability)→ Articles VI, XII
nexus_context       → Contextualize                        → Capability 4
nexus_planning      → Plan (+ Exec-Strategy/Skills/Packaging merged) → Capability 5; Simplification 1
nexus_orchestration → Coordinate                           → Capability 6; INV-37/23
nexus_harness       → Foundation (Harness category)        → Article IX; INV-34/35/36
nexus_runtime       → Foundation (Runtime Manager/Registry)→ Article IX; INV-36
nexus_runtime_adapters → Foundation (adapter selection)    → Article IX; INV-37
nexus_runtime_claude/gemini/shell → Execute (Runtime backends) → Capability 7; Article I
nexus_execution     → Execute (Execution Engine)           → Capability 7; INV-04/21
nexus_validation    → Validate                             → Capability 10; INV-20
nexus_recovery      → Recover                              → Capability 11; INV-22
nexus_reflection    → Reflect                              → Capability 12; INV-25
nexus_knowledge     → Learn                                → Capability 13; INV-24/26
nexus_workflows     → (spine runner + prototype seeds)     → transitional; hosts §7 promotions
nexus_operator/briefings → Operate (surface)               → Capability 15 (re-home)
nexus_research      → (domain vertical)                    → transitional consumer
```

**Capabilities with no package yet (to create/promote):**
```
Understand → nexus_intent            (new; wrap v1 openrouter as its runtime capability)
Reason     → nexus_engineering       (new; the EI corpus; hosts Estimation)
Ground     → nexus_repository        (promote nexus_workflows/repo_profile) + Operator Profile + Knowledge
Govern     → nexus_policy            (extract v1 policy_service/defaults) + nexus_human_interaction (promote human_approval + wrap v1 Discord)
Act        → nexus_actuation         (promote git_actions + wrap v1 sandbox)
Operate    → nexus_operations        (migrate v1 metrics/briefing) + Estimation (in nexus_engineering)
Foundation → durable Memory          (reuse v1 nexus/memory behind nexus_core Repository protocol)
```

---

## 3. Legacy Migration (v1 subsystem → verdict)

| v1 subsystem | Verdict | Why | Constitutional destination |
|---|---|---|---|
| Discord (`communication/discord`) | **Wrap** | Real, owner-checked, working; users depend on it | Human Interaction *Channel Adapter* (INV-34) |
| Email (`communication/email`) | **Wrap** | Working transport | Communication Harness |
| Chat planner (`communication/chat/planner.py`) | **Replace (strangle)** | LLM choice overridden by regex = the ad-hoc "thinking" EI exists to own | Reason (Engineering Intelligence) |
| Scheduler (`scheduling/scheduler.py`) | **Keep** | Real APScheduler; Foundation need | Foundation Scheduler |
| v1 orchestrator (`scheduling/orchestrator.py`) | **Strangle** | Hardcoded runtime default; ad-hoc coordination | Coordinate (nexus_orchestration) |
| Memory (`memory/*`) | **Migrate (asset)** | The durable substrate v2 lacks | Foundation durable Memory behind `nexus_core` Repository protocol |
| Approvals (`approvals/service.py`) | **Wrap + migrate** | Real fail-closed owner semantics (A-001) | Govern: requirement→Policy Engine, surface→Human Interaction, outcome→approver |
| Policy (`memory/policy_service.py`, `core/policy_defaults.py`) | **Migrate (asset)** | INV-28 mandates a single Policy Engine; v1 has the seed | nexus_policy (Policy Engine) |
| Execution runners (`execution/runners`) | **Replace (gradually)** | Duplicates v2 adapters; INV-36 forbids two registries | Execute via v2 Runtime |
| Sandbox (`execution/sandbox`) | **Wrap** | Real Docker/subprocess isolation | Act (nexus_actuation) environment/permission enforcement |
| Execution governance (`execution/governance.py`) | **Migrate** | Governance rules | Policy Engine |
| Outbox (`gateway/*`) | **Keep** | Real, reliable delivery | Foundation Outbox |
| Metrics/Briefing (`core/metrics.py`,`intelligence/briefing.py`) | **Migrate** | Operations seed; fix the in-memory-reset defect | Operate (nexus_operations) |
| OpenRouter client (`intelligence/openrouter.py`) | **Wrap** | LLM transport | a Runtime capability consumed by Understand/Reason (INV-32) |
| Research (`intelligence/research.py`) | **Migrate** | A domain vertical | rebuild on real pipeline (parallels nexus_research) |
| `agents/` (Hermes) | **Replace** | Overlaps v2 runtime | Execute via v2 Runtime |
| API/host (`api.py`,`__main__.py`) | **Keep (retire last)** | The strangler host | remains until traffic fully moved |

**Nothing in v1 is deleted before its constitutional owner exists and traffic has moved.** Delete order is
§9.

---

## 4. Migration Graph (Current → Intermediate → Constitutional)

```
CURRENT (two disconnected strata)
  v1 host (Dex/API) ── owns ──► durable Memory, Policy seed, Approvals/Discord, Scheduler, Outbox, Sandbox, Runners, Metrics
  v2 spine (orphan) ── owns ──► Context, Plan, Coordinate, Execute, Validate, Recover, Reflect, Learn, Runtime (in-memory, unwired)

        │  Stage 1: bind v2 repos → v1 durable store (Repository protocol); no behavior change
        ▼
INTERMEDIATE-A (shared durable substrate)
  v2 spine now durable; v1 unchanged. Releasable.

        │  Stage 2: extract Policy Engine (nexus_policy) from v1 policy seed; both call it
        │  Stage 3: first seam — route v1 runtime-selection through v2 Coordinate (shadow → flag)
        ▼
INTERMEDIATE-B (governance unified + first strangled decision)
  One Policy Engine; one runtime decision flows through the constitution behind a flag. Releasable.

        │  Stage 4: promote prototypes → nexus_repository, nexus_human_interaction (wrap Discord), nexus_actuation (wrap sandbox)
        │  Stage 5: build reasoning heads → nexus_intent (Understand), nexus_engineering (Reason)
        ▼
INTERMEDIATE-C (constitutional capabilities exist, wired behind flags)
  Understand→Reason→Plan→Coordinate→Execute→Act→Validate→Recover→Reflect→Learn runs for ONE real workflow in prod (flagged). Releasable.

        │  Stage 6: raise flags per task type (shadow → canary → default). Stage 7: Operations/Estimation. Stage 8: retire duplicates.
        ▼
CONSTITUTIONAL
  Production traffic flows through the capability spine on cross-cutting planes; v1 reduced to Channel Adapters + shared durable store; duplicates removed.
```

**No arrow is a big-bang.** Every transition is additive and flag-gated; the losing v1 path stays live
until its replacement carries traffic in shadow, then canary, then default.

---

## 5. ADR Roadmap

The Constitution flagged rulings needing formal ratification. These ADRs enact them; none changes an
existing invariant (INV-01…39 remain intact — they were shown to already support these rulings).

| ADR | Decision | Why needed | Risk | Migration impact |
|---|---|---|---|---|
| **ADR-005** | Reinstate **Engineering Intelligence** as the *Reason* capability; retire the name "Executive Intelligence"; move "classify work / estimate complexity" from Intent Resolution to EI | Resolves the numbered-vs-engineering fork; INV-02 already requires the split | Low (no invariant change; no code yet exists for either) | Unblocks `nexus_engineering` (Stage 5); Intent Resolution scope narrows |
| **ADR-006** | Name **Policy Engine, Repository Intelligence, Human Interaction, Actuation, Operations** as first-class subsystems with their own packages | INV-28 already mandates Policy; the rest are constitutional capabilities without packages | Low | Authorizes Stages 2/4/7 package creation |
| **ADR-007** | Adopt a **durable persistence backend** behind `nexus_core`'s `Repository`/`EventStore` protocols, reusing v1's SQLAlchemy/Alembic store; supersede "v2 is in-memory" | Every learning/graph/checkpoint/long-wait claim depends on durability | **Medium** (data-path change) | Stage 1; must preserve replay-equivalence (INV-13/14) |
| **ADR-008** | Declare v2 the **target platform** and define the **v1→v2 strangler seam** (shadow-mode + feature-flag cutover, per-decision) | Makes the integration strategy an official, testable contract | Medium | Governs Stages 3–8; defines flags and shadow protocol |
| **ADR-009** | **One runtime registry** (INV-36): make v2's `AdapterRegistry`/Harness Registry authoritative; adapt v1 runners as legacy adapters, then retire | Two registries violate INV-36; duplicate ownership | Medium | Stage 3/8; removes a duplicate |
| **ADR-010** *(optional, later)* | Freeze the **proposed contracts** (Engineering Strategy, Repository Understanding, Environment/Session, Interaction, Estimation) as each second consumer appears | INV-07 discipline; freeze only when depended upon | Low | Stages 4–7, incrementally |

Sequencing: 005+006 (docs, Stage 0) → 007 (Stage 1) → 008 (Stage 3) → 009 (Stage 3/8) → 010 (as needed).

---

## 6. Package Evolution (per package: keep/split/merge/rename/deprecate/replace)

Only strongly-justified changes.

| Package | Action | Justification |
|---|---|---|
| `nexus_core`, `nexus_context`, `nexus_orchestration`, `nexus_execution`, `nexus_runtime*`, `nexus_validation`, `nexus_recovery`, `nexus_reflection` | **Keep** | Already constitutional; no reshape. |
| `nexus_infra` | **Keep + extend** | Add a durable backend behind existing protocols (ADR-007). No API change. |
| `nexus_planning` | **Keep + absorb** | Merge Execution-Strategy/Skill-Selection/Work-Packaging *facets* into it (Constitution Simplification 1) — they are already partly here; formalize ownership, don't split. |
| `nexus_knowledge` | **Keep + split concern** | Keep the Learn engine; **split out** grounding (Repository/Operator/Execution intelligence are separate packages, not Knowledge). |
| `nexus_harness` | **Keep** | Harness category model is correct. |
| `nexus_workflows` | **Split** | Extract prototypes → new packages (§7); keep `pipeline.py`/`coordinator.py` as the *spine runner* (reshape the linear coordinator to compose capabilities); retire `a0.py`/`a1.py` into real verticals. |
| `nexus_operator` + `nexus_briefings` | **Merge → `nexus_operations`** | Both are the Operate surface; one plane, one package. |
| `nexus_research` | **Keep (re-wire)** | A domain vertical; point it at the real pipeline. |
| — | **Create** `nexus_intent` | Understand capability (new). |
| — | **Create** `nexus_engineering` | Reason capability + Estimation (ADR-005). |
| — | **Create** `nexus_repository` | Promote `repo_profile.py`/`repo_intelligence.py`. |
| — | **Create** `nexus_policy` | Extract v1 policy seed (ADR-006). |
| — | **Create** `nexus_human_interaction` | Promote `human_approval.py` + wrap v1 Discord adapter. |
| — | **Create** `nexus_actuation` | Promote `git_actions.py` + wrap v1 sandbox. |
| v1 `nexus/execution/runners`, `nexus/agents` | **Deprecate → replace** | Duplicate runtime (INV-36); strangle onto v2 Runtime. |
| v1 `nexus/approvals` | **Deprecate → wrap** | Fold into Policy Engine (requirement) + Human Interaction (surface). |
| v1 `nexus/core/metrics` | **Deprecate → migrate** | Into `nexus_operations`; fix in-memory-reset defect. |

---

## 7. Critical Refactors (ranked by leverage)

Leverage = how many future capabilities a refactor unblocks. Each is additive.

1. **Durable Memory substrate (reuse v1 DB behind v2 protocols).** *Unblocks:* Knowledge graph, learning
   across runs, checkpoints/resume, long-wait Human Interaction, Operations history, Reflection ≥2-episode
   persistence. **Every durability claim depends on this.** Lowest-cost highest-return: v1's SQLAlchemy
   store already exists; bind it behind `nexus_core.persistence` without changing v2 call sites. **Rank 1.**
2. **Policy Engine (`nexus_policy`, from v1 policy seed).** *Unblocks:* every governed action — EI's
   proposed gates, Actuation's permission enforcement, Human Interaction's approval-required, fail-closed
   safety (INV-28/30). A universal dependency; must become a leaf. **Rank 2.**
3. **v1→v2 integration seam (strangler, ADR-008).** *Unblocks:* all production value; connects the orphaned
   spine; makes every later capability shippable. **Rank 3** (must follow 1–2 so the seam has a durable,
   governed target).
4. **Engineering Intelligence (`nexus_engineering`).** *Unblocks:* the vision's core — Nexus actually
   *thinking about execution* (classify/estimate/approach/rigor/autonomy). Depends on grounding + policy.
   **Rank 4.**
5. **Repository Intelligence (`nexus_repository`, promote `repo_profile`).** *Unblocks:* grounded EI +
   Context; the A2 prototype is a running head-start. **Rank 5.**
6. **Human Interaction (`nexus_human_interaction`, wrap Discord).** *Unblocks:* unattended governed
   autonomy (the approval channel three corpora named as the shared blocker). **Rank 6.**
7. **Operations + Estimation (`nexus_operations`).** *Unblocks:* cost/health/performance visibility and
   EI's risk calibration. **Rank 7.**

Identity/RBAC (freeze `G-1`) rides inside Policy Engine + Human Interaction; not a separate early refactor.

---

## 8. Integration Strategy (v1 → v2 without breaking users)

**Pattern: Strangler Fig with shadow-mode, per-decision, flag-gated.** The known biggest issue is the v1/v2
disconnection; this is how production gradually moves onto the constitutional platform.

**Step 1 — Shared substrate (no behavior change).** Bind v2's repositories to v1's durable store behind the
`Repository` protocol (Stage 1). v1 and v2 now share truth; neither's behavior changes. Replay-equivalence
(INV-13/14) is the safety net: state is a projection of the event log, so a bad projection is rebuildable.

**Step 2 — Shadow mode (compute, log, do not act).** For one weak v1 decision — start with **runtime
selection** (`nexus/scheduling/orchestrator.py`'s `task.runtime_id or "gemini"`) — call the v2 capability
in parallel, record what it *would* choose as an event, but **let v1 act**. Compare over real traffic. Zero
user impact; pure observation. This is the safest possible integration probe.

**Step 3 — Canary flag (act for a slice).** When shadow divergence is understood and acceptable, a feature
flag routes a small slice (e.g. one task type, one owner) through the v2 decision; v1 remains the default.
Fail-closed (INV-30): any v2 error falls back to v1's path.

**Step 4 — Default flip, then strangle.** Raise the flag to default; keep v1's code as fallback for one
release; then remove the v1 decision. Repeat per decision: runtime selection → approval requirement →
coordination → context → planning → the full spine.

**Order of decisions to strangle** (weakest/safest first): runtime selection → approval-required (onto
Policy Engine) → validation/completion → coordination → context assembly → planning/decomposition →
intent+strategy (Understand+Reason last, since they need everything grounded).

**Users never break because:** flags default to v1; v2 runs in shadow before it ever acts; every governed
action fails closed to the existing safe path; Discord/email channels are *wrapped, not replaced*, so the
operator-facing surface is unchanged throughout.

---

## 9. Technical Debt Removal (with safe order)

Remove only **after** the constitutional owner exists **and** traffic has moved (never before).

| Debt | Duplicate today | Remove when | Order |
|---|---|---|---|
| Duplicate **persistence models** | v1 `memory/models` vs v2 in-memory repos | v2 bound to v1 store (Stage 1) | **1** (converge, don't delete) |
| Duplicate **runtime registry** | v1 `execution/runners`+`agents` vs v2 `AdapterRegistry` | v2 registry authoritative + carries traffic (ADR-009, Stage 3) | **2** |
| Duplicate **policy/governance** | v1 `policy_service`/`execution/governance` vs `nexus_policy` | Policy Engine carries governed decisions (Stage 2) | **3** |
| Duplicate **approvals** | v1 `approvals/service` vs v2 `human_approval` | Human Interaction + Policy carry approvals (Stage 4) | **4** |
| Duplicate **metrics** | v1 `core/metrics` vs v2 observability | `nexus_operations` computes from the log (Stage 7) | **5** |
| Transitional abstraction: `StubClaudeInvoker` as prod default | — | Real invoker on the prod path (Stage 6) | **6** (keep stub for tests) |
| Transitional: `WorkflowCoordinator` linear harness; `a0.py`/`a1.py` demos | — | Reshaped into the spine runner; verticals real (Stage 5–6) | **7** |
| Obsolete **terminology** | "Executive Intelligence", "12 layers", "Supervision layer", "Communication service"/"Channel Harness" | Docs at Stage 0; code as packages land | **8** (continuous) |

Debt-removal principle: **converge first (share one implementation), then delete the loser.** Deleting
before convergence is how a strangler turns into an outage.

---

## 10. Migration Stages (each compiles, tests, releasable)

No stage leaves an unstable halfway architecture. Each ends releasable; v1 keeps running throughout.

**Stage 0 — Ratify (docs only).** Adopt the Constitution as canonical; land ADR-005/006. Retire obsolete
terminology in docs. *Releasable: trivially (documentation).*

**Stage 1 — Durable substrate (ADR-007).** Add a durable backend behind `nexus_core`'s Repository/EventStore
protocols, reusing v1's DB (or SQLite for v2 tests). v2 call sites unchanged; v1 unchanged. *Test gate:
existing v2 unit tests pass + a replay-equivalence test (INV-14). Releasable.*

**Stage 2 — Policy Engine (`nexus_policy`, ADR-006).** Extract v1 policy logic behind the `policy.md`
contract; fail-closed default (INV-30). Both v1 and v2 may call it; nothing forced to yet. *Test gate:
differential tests vs v1 policy outcomes. Releasable.*

**Stage 3 — First seam + one registry (ADR-008/009).** Runtime-selection shadow mode in v1's orchestrator;
make v2's registry authoritative for the shadow path. Flag defaults off. *Test gate: shadow divergence
logged; flag-off = byte-identical v1 behavior. Releasable.*

**Stage 4 — Promote prototypes.** `nexus_repository` (from `repo_profile`), `nexus_human_interaction` (from
`human_approval` + Discord Channel Adapter), `nexus_actuation` (from `git_actions` + wrap sandbox). Additive
packages, unit-tested, unwired to prod except behind flags. *Releasable.*

**Stage 5 — Reasoning heads.** `nexus_intent` (Understand; wrap v1 openrouter as its runtime capability),
`nexus_engineering` (Reason + Estimation; ADR-005). Emit Goal → Engineering Strategy for a flagged workflow;
downstream still the existing pipeline. *Test gate: determinism-seam test (recorded strategy replays,
INV-17). Releasable.*

**Stage 6 — First end-to-end constitutional workflow in prod (flagged).** Wire one real task type through
Understand→Reason→Plan→Coordinate→Execute→Act→Validate→Recover→Reflect→Learn, on the durable store, governed
by Policy, approved via wrapped Discord, executed on the real Runtime. Shadow → canary → default. *Releasable
per flag level.*

**Stage 7 — Operations/Estimation (`nexus_operations`).** Merge `nexus_operator`+`nexus_briefings`; compute
real metrics/cost from the event log; fix the in-memory-reset defect. *Releasable.*

**Stage 8 — Strangle & retire duplicates.** As each capability carries default traffic, remove the
corresponding v1 ad-hoc path (order §9). Keep v1 Channel Adapters + shared durable store. *Releasable; v1
host retires last.*

---

## 11. Risks

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | Big-bang temptation to "just rewrite v1 on v2" | Med | High | Strangler + flags are mandatory (ADR-008); no stage rewrites a running path |
| R2 | Durable-substrate migration corrupts/loses state | Med | High | Additive behind Repository protocol; replay from event log (INV-13/14); differential + replay-equivalence tests before cutover |
| R3 | Two runtime registries drift during coexistence | Med | Med | Make v2 authoritative early (ADR-009, INV-36); v1 runners adapted, not maintained |
| R4 | Policy extraction regresses to fail-open | Low | High | Default-deny (INV-30); differential tests vs v1 outcomes; shadow before act |
| R5 | Real-runtime cost/rate limits during integration (account near limit) | High | Med | Stub-by-default; real Runtime only behind flag; shadow uses no real execution |
| R6 | Users notice behavior change | Med | Med | Flags default to v1; shadow-mode first; channels wrapped not replaced |
| R7 | Prototype promotions carry demo-grade assumptions into prod | Med | Med | Freeze each contract (ADR-010) only when a 2nd consumer appears; harden before flag-on |
| R8 | "Ratify and freeze" of five corpora ossifies contradictions | Low | High | Only *this* Constitution is canonical; corpora are subordinate detail (Stage 0) |

**Root mitigation:** every risk is contained by the same three disciplines — *share before delete, shadow
before act, flag before default.*

---

## 12. Final Recommendation

**Converge; do not rebuild.** The repository already holds both constitutional halves — v2's reasoning/
execution spine and v1's durable Foundation/Governance — accidentally split into two disconnected strata.
The migration is to **wire them into one constitutional platform via a per-decision strangler**, in this
order of leverage: **durable substrate → Policy Engine → first production seam → Engineering Intelligence →
Repository Intelligence → Human Interaction → Operations.** Three of the six "missing" capability packages
are **promotions of prototypes that already run** (`repo_profile`, `human_approval`, `git_actions`); two
Foundation "voids" (durable Memory, Policy Engine) are **harvests of working v1 code**; only two capabilities
(Intent Resolution, Engineering Intelligence) are genuinely new — and they come last, once everything they
reason over is grounded, governed, and durable.

Sequenced as eight additive, releasable stages, with shadow-mode and feature flags at every seam, Nexus
reaches the constitutional architecture **without a single big-bang rewrite and without breaking the
running Dex product at any point.** The first move — binding v2 to a durable store behind protocols it
already defines — is low-cost, high-leverage, and changes no behavior; it is the correct place to start.

**One-line recommendation.** *Do not build the Constitution — converge onto it: share v1's durable
substrate behind v2's protocols, extract the Policy Engine, then strangle v1's ad-hoc decisions onto the
constitutional capabilities one flag at a time, promoting the three running prototypes and building only
Intent Resolution and Engineering Intelligence new — releasable at every step, breaking no user.*

---

*This is a migration strategy. It modifies no invariant, contract, ADR, or architecture, and recommends no
code. It sequences how the existing repository becomes the constitutional architecture additively and
releasably. The Constitution is law; this blueprint is the route.*
