# Nexus — Architecture Freeze Review v1

Status: **Audit / checkpoint document.** Not a design exercise, not implementation.
Author role: Chief Architect approving (or refusing) production implementation, joining today.
Deliverable of the Architecture Freeze Audit. Creates no code, amends no ADR/contract/invariant,
modifies no existing document, commits nothing.

Verdict headline: **APPROVED WITH CONDITIONS.** The design corpus is ratifiable and stable. But the
audit found a reality the prior "architecture is complete" reviews understated: Nexus is **three
misaligned strata**, its single most important capability (real governed actuation) is a **stub on
every validated path**, and the three most recently "frozen" architectures have **zero code**. Freeze
the design — but freeze it *honestly*, quarantine the unproven frontier, and make the next milestone a
real end-to-end actuation, not more foundational design.

---

# 0. Method & evidence base

This audit read the design corpus (`docs/v2/**`, `adr/`, `contracts/`, `blueprint/`) **and** measured
the code, because a freeze that only reads the docs certifies intentions, not reality. Hard evidence
gathered first-hand this pass:

- **Code volume (v2 `nexus_*`):** 20 packages, ~24,000 non-test source LOC.
- **Tests:** 186 test files / ~37k test LOC / **2,218 unit test functions**; **zero** tests co-located
  in the `nexus_*` packages — all live in `tests/`. Unit tests import v2 engines heavily
  (`nexus_core` ×101, `nexus_runtime` ×44, `nexus_execution` ×26, `nexus_validation` ×23).
- **Running product:** v1 `nexus/` (11,739 LOC), a FastAPI + Discord ("Dex") governed-execution
  console. `python -m nexus` starts the ASGI server; the `nexus_*` engines are **not** on that path.
- **Integration seam:** grep confirms **v1 does not import v2, and v2 does not import v1.** They are
  disjoint.
- **Actuation reality:** every runtime adapter defaults to a `Stub*Invoker`; the real
  `ClaudeCliInvoker`/`GeminiCliInvoker` (real `subprocess.Popen` to the CLI) exist but are opt-in
  "smoke" paths. `WorkflowCoordinator` defaults to `StubClaudeInvoker`. v1's own runners are
  classified "Stubbed — generic shell runner, no real CLI binary" (`blueprint/STATUS.md`).
- **`MIGRATION_FROM_V1.md`** is explicitly **conceptual only** — "does not describe code, data, or
  deployment migration."

Everything below is anchored to that evidence.

---

# Phase 1 — Repository walkthrough (the mental model)

Nexus today is **three strata that do not line up**:

```
STRATUM 1 — RUNNING PRODUCT          STRATUM 2 — v2 ENGINE TIER            STRATUM 3 — v2 DESIGN TIER
nexus/  (v1.0.x, 11.7k LOC)          nexus_*  (~24k LOC, 2218 unit tests)  docs/v2/** (26 numbered +
FastAPI + Discord "Dex"              10 cognitive engines + core/infra     5 design packages)
governed-execution console           + 4 capability packages
                                     + WorkflowCoordinator (composes 10)
─────────────────────────────       ─────────────────────────────────    ────────────────────────────
ACTUALLY RUNS.                       BUILT + UNIT-TESTED IN ISOLATION.     PURE DESIGN.
Runtimes = stub shell runners.       Validated path = StubClaudeInvoker.   engineering / actuation /
Claude/Gemini "no real binary".      NOT wired to v1. No entrypoint.        human_interaction = 0 code.
   │                                    │                                      │
   └──── disjoint (no imports) ─────────┘                                      │
                                     └──── partially realized by ─────────────┘
```

- **Stratum 1 (v1, `nexus/`)** is the honest, released, *attended* control plane: un-bypassable
  approval gate, 11-gate governance, event-sourced audit log, transactional/communication outbox,
  scheduler, Discord CRUD. Its execution runtimes are stubs. This is what the Discord operator actually
  talks to — and why "Dex" cannot open Claude Code, cannot send email, and reports
  `generic_command not found`.
- **Stratum 2 (v2 engines, `nexus_*`)** is a clean-room reimplementation of the pipeline in
  `docs/v2/`: `nexus_core`/`nexus_infra` + ten cognitive engines (context, planning, orchestration,
  harness, execution, runtime, validation, recovery, reflection, knowledge) + four capability packages
  (workflows, research, briefings, operator) + three runtime adapters (claude, gemini, shell). A
  `WorkflowCoordinator` composes all ten engines into one deterministic Goal→Knowledge flow. It is
  well-tested **as a library** and disconnected from anything that runs.
- **Stratum 3 (design, `docs/v2/**`)** is the largest and most coherent asset: 26 numbered specs, 39
  invariants, 4 ADRs, 18 contracts, and five design packages (`runtime`, `knowledge` — realized in
  Stratum 2; `engineering`, `actuation`, `human_interaction` — **not** realized anywhere).

**Dependency direction** within Stratum 2 is clean and matches the invariants: engines import only
`{nexus_core, nexus_infra}`; the coordinator performs the sanctioned projections; ADR-001 event
sourcing, ADR-002 registries, ADR-003 object model, ADR-004 policy/approval taxonomy are respected in
the built code. The architecture *within a stratum* is sound. The failure is *between* strata.

---

# Phase 2 — Original vision alignment

Reference request: *"Open Claude Code in D:/port, understand the repo, investigate the bug, follow my
methodology, ask clarifications, obtain approvals, execute safely, validate independently, recover,
learn, and report back."*

| Vision capability | Status | Evidence |
|---|---|---|
| Normalize a request into a Goal | **Partial** | `nexus_core/domain/intent.py` exists as a *type*; there is **no Intent Resolution engine** package — the "understand the request" layer is a data class, not a resolver. |
| Assemble context before acting | **Achieved (isolated)** | `nexus_context` built + tested; not fed by a real repository reader. |
| Plan / decompose into governed work | **Achieved (isolated)** | `nexus_planning`, execution graph, strategy built + tested. |
| Follow *my* engineering methodology | **Missing** | The `engineering` (Engineering Intelligence) design is **0 code**; nothing selects an approach/methodology. |
| Ask clarifications | **Missing (as capability)** | `human_interaction` design is **0 code**; v1 has ad-hoc Discord chat only. |
| Obtain approvals | **Achieved (v1) / isolated (v2)** | v1 approval gate is the strongest real asset; v2 carries ADR-004 taxonomy but no human surface. |
| Execute safely in a real environment | **Missing** | `actuation` design is **0 code**; every validated runtime path is a **stub**; the governed Session/Environment/Workspace substrate does not exist. |
| Validate independently | **Achieved (isolated)** | `nexus_validation` built + tested against evidence (INV-20). |
| Recover | **Achieved (isolated)** | `nexus_recovery` built + tested. |
| Learn | **Achieved (isolated)** | `nexus_reflection` → `nexus_knowledge` built; coordinator reads Knowledge into Planning (INV-26). |
| Report back | **Achieved (v1) / isolated (v2)** | v1 Discord/briefings real; v2 operator/briefings packages built but unwired. |

**Alignment verdict: the cognitive spine is real and tested; the *hands, the methodology, and the
mouth* are not.** Nexus can, in a test harness, reason a stubbed task from Goal to validated Knowledge.
It **cannot today** open a real Claude Code, operate a real repo under governance, ask a real human a
clarifying question through a governed surface, or report through the same pipeline — because
Actuation, Human Interaction, and Engineering Intelligence are unbuilt and the runtime is a stub. The
reference request fails at *"open Claude Code … execute safely."*

**Improved beyond the original vision:** the event-sourced determinism seam (INV-17: cognition/human
input captured once as data, replay never re-infers/re-asks), the evidence-over-self-report validation
model (INV-20), and the strict provider-independence (capabilities, not models) are genuine
advances over the v1 "run the task" framing and over the original ask.

---

# Phase 3 — Architecture audit (per subsystem)

| Subsystem | Design | Code | Cohesion / coupling | Determinism | Observability | Notes |
|---|---|---|---|---|---|---|
| Intent Resolution | ✅ (`16`) | 🟠 type only | n/a | — | — | No engine; normalization unbuilt. |
| Context | ✅ (`03`) | ✅ tested | high / clean | ✅ | events | Not fed by real sources. |
| Planning | ✅ (`04`) | ✅ tested | high / clean | ✅ | events | Sound. |
| Orchestration | ✅ (`07`) | ✅ tested | high / clean | ✅ | events | Owns runtime selection (INV-37). |
| Harness | ✅ (`11`) | ✅ tested | high / clean | ✅ | registry | Skill/policy resolvers present. |
| Execution | ✅ (`08`) | ✅ tested | high / clean | ✅ | `execution.*` | Emits candidates only (INV-12). |
| Runtime | ✅ (`15`,`runtime/`) | ✅ tested | high / clean | ✅ | `runtime.*` | **Validated path = stub.** |
| Runtime adapters (claude/gemini/shell) | ✅ | 🟡 stub-default | clean | ✅(stub) | — | Real CLI invokers exist, opt-in only, unproven. |
| Validation | ✅ (`14`) | ✅ tested | high / clean | ✅ | reports | Strong; evidence-based. |
| Recovery | ✅ (`19`) | ✅ tested | high / clean | ✅ | plans | Sound. |
| Reflection → Knowledge | ✅ (`26`,`10`) | ✅ tested | high / clean | ✅ | candidates/graph | Learning loop wired in coordinator. |
| Supervision | ✅ (`09`) | 🔴 **not found** | — | — | — | Designed, **unbuilt**. |
| Governance / Policy Engine | ✅ (`12`,`20`) | 🟡 partial | — | ✅ | audit | `policy` is a domain type + resolvers; no standalone deterministic Policy Engine surfaced. |
| Skills | ✅ (`06`) | 🟡 partial | — | — | — | Type + resolvers; no skill library / execution. |
| Engineering Intelligence | ✅ (`engineering/`) | 🔴 **0 code** | — | — | — | Newly frozen; unbuilt. |
| Execution Actuation | ✅ (`actuation/`) | 🔴 **0 code** | — | — | — | Newly frozen; unbuilt. **This is the missing hands.** |
| Human Interaction | ✅ (`human_interaction/`) | 🔴 **0 code** | — | — | — | Newly frozen; unbuilt. |
| Operator / Research / Briefings | ✅ | ✅ tested | clean | ✅ | — | Built but unwired to a live operator surface. |

**Cross-cutting:** determinism, replayability, and event-model discipline are the strongest properties
of the built code and are consistently honored. **Security/identity, scalability, and deployment are
the weakest** — there is no identity/RBAC, no approver-identity model (HI G-1), no distributed
substrate, and no deployment path for Stratum 2. Observability exists at the event level but there is
no operational telemetry/metrics wiring for the v2 tier (v1 has metrics).

---

# Phase 4 — Gap analysis (evidence-backed)

**Critical (block the vision, not the freeze):**
1. **Real governed actuation does not exist.** Actuation package = 0 code; validated runtime path =
   stub on every stratum. Nexus cannot safely operate a real external environment. *This is the single
   most consequential gap and the one the design has least earned the right to freeze* (never validated
   against a real process).
2. **The three newest "frozen" architectures are unbuilt** (engineering, actuation, human_interaction).
   Freezing a design that has never met a compiler or a real environment is the highest-risk kind of
   freeze.
3. **v1 and v2 are disjoint with no code/deployment migration.** `MIGRATION_FROM_V1.md` is conceptual
   only. Risk: a permanent fork — a running-but-primitive v1 and a well-designed-but-unwired v2.

**Major:**
4. **Intent Resolution, Supervision, and a standalone Policy Engine are designed but not built** (type
   stubs / resolvers only). The pipeline the coordinator "composes" silently omits these.
5. **Approver identity & authorization** (HI G-1): the platform records *who answered* but cannot
   adjudicate *who may answer* — a governance hole for any real approval.
6. **Repository Intelligence** remains named-but-undesigned; decision quality is bounded by an
   ungrounded understanding of the target repo (`engineering/10`).

**Minor / documentation / operational:**
7. **Honest-labeling gap:** "2,218 unit tests green / 20 engines" reads as "operational" but the
   validated path is a stub; the freeze must say so.
8. **No identity/RBAC, telemetry, metrics, scheduling, deployment, or scaling** for Stratum 2
   (Phase D of the roadmap is entirely greenfield).
9. **Version-string drift** persists (in-code `0.1.0` vs release tags) — cosmetic but a governance
   smell for a freeze checkpoint.

---

# Phase 5 — Drift analysis

**Classification: MINOR-to-MODERATE drift — but a *stratification* drift, not a *direction* drift.**
The design never wandered off-vision; the *implementation* forked away from the *running product* and
the *validated path* drifted to permanent stubs. That is drift between layers, which is more dangerous
than conceptual drift because it hides behind green tests.

| Axis | Estimate | Justification |
|---|---|---|
| **Alignment with original vision (end-to-end, for real, today)** | **~35–40%** | Cognitive spine (context→…→knowledge) real and tested = strong middle; but methodology, hands (actuation), and human surface unbuilt, runtime stubbed, nothing integrated. The reference request cannot run for real. |
| **Architecture completion** | **~90%** | Comprehensive, internally consistent corpus (26 specs, 39 invariants, 4 ADRs, 18 contracts, 5 packages). Remaining *design* gaps: Repository Intelligence, approver identity, and a real (non-conceptual) integration/migration architecture. |
| **Implementation completion (of the designed architecture)** | **~45–50%** | ~10 of ~15 core engines built + unit-tested; but 3 newest subsystems 0-code, Intent/Supervision/Policy-Engine/Skills thin-or-absent, actuation validated only as stub, no integration/identity/deployment, v1↔v2 unmerged. |

**Acceptable drift:** building the deterministic cognitive engines ahead of the runtime, and keeping a
stub as the *CI/replay* path (it is the correct reproducible-test substrate per INV-17). Designing
Actuation/HI/EI before building them is also acceptable — *provided the freeze does not certify them as
proven.*

**Drift that must be corrected:** (a) the stub being the *only validated* path — no evidence any real
governed actuation has ever succeeded; (b) the v1/v2 disjunction with no code migration; (c) the
review narrative that repeatedly declared the architecture "complete / next epoch is implementation"
while three of its own newest pillars had 0 code and the cognitive engines were already largely
implemented — the reviews both **over-credited design completeness** and **under-credited (and
mis-described) implementation state**.

---

# Phase 6 — Architecture Freeze v1 decision

## **APPROVED WITH CONDITIONS.**

*Why not APPROVED:* three newly "frozen" pillars have zero code, the actuation model has never touched
a real environment, and v1↔v2 has no integration architecture. Certifying that as an unconditional
freeze would repeat the exact over-confidence this audit is meant to catch.

*Why not NOT READY:* the design corpus is genuinely mature, internally consistent, invariant-preserving,
and — for the ten cognitive engines — already validated in code. There is no *foundational* subsystem
whose absence invalidates the design. The remaining gaps are *grounding, identity, integration, and
real actuation* — all extensions of, or realizations of, the existing seams, not new pillars.

**Conditions for the freeze to hold:**

- **C1 — Quarantine the unproven frontier.** Mark `actuation`, `runtime` (real-invoker path), `engineering`,
  and `human_interaction` as **PROVISIONALLY FROZEN**: ratified as design, *not* certified until a real
  end-to-end actuation validates them. Design that has never operated a real `claude` process may not
  carry the same freeze status as code with 2,218 passing tests.
- **C2 — Add the two named-but-missing design seams** the prior reviews deferred: **Repository
  Intelligence** (grounding) and **Approver Identity/Authorization** (Governance extension, HI G-1). A
  seam each, not full subsystems, is enough to freeze around.
- **C3 — Author a *real* v1→v2 integration/migration architecture** (code, data, deployment), replacing
  the conceptual-only `MIGRATION_FROM_V1.md`. Without it the freeze blesses a fork.
- **C4 — Correct the record.** This document supersedes any prior claim that "the architecture is
  complete and the only remaining work is implementation." State plainly that the validated execution
  path is a stub and that ~half the designed architecture is unbuilt.

---

# Phase 7 — Implementation roadmap

## Phase A — Realize the frozen architectures (highest leverage first)

Do **not** build the three new subsystems in isolation. Build them **through one vertical slice** that
also validates the freeze:

- **A0 (the milestone that unblocks everything): one real, governed, end-to-end actuation.** Take the
  existing `WorkflowCoordinator`, swap `StubClaudeInvoker` for a **governed** real actuation of `claude`
  in a real Workspace over a real repo, behind an approval gate **answered on a real channel**, running
  the reference request ("investigate → fix → validate → commit → report") to success **once, for real.**
  This single slice forces the first thin versions of **Execution Actuation** (governed Session over
  the real process), **Human Interaction** (the approval/clarification surface), and **Engineering
  Intelligence** (choose the approach + place the gate) into existence, and *proves or breaks* the
  provisional freeze (C1) with evidence instead of assertion.
- **A1–A3:** harden each of Actuation / Human Interaction / Engineering Intelligence from the thin slice
  to the full frozen design, guided by what A0 reveals.

## Phase B — Repository Intelligence

**Recommendation: an Engineering Intelligence *capability*, promoted to its own subsystem only when a
second consumer needs it** — not a standalone pillar on day one. Justification: its sole current
consumer is Engineering Intelligence ("how well do we understand this repo before deciding the
approach"); the design (`engineering/10`) already treats it as a bounded grounding concern with a fixed
seam. Building it as an EI capability avoids premature subsystem ceremony while honoring the seam; the
freeze needs only the seam (C2), not the subsystem.

## Phase C — External integrations (realize the actuators/harness/channels)

Claude Code, Gemini CLI, Shell, Git, Docker, MCP → **Actuators behind the Runtime Adapter boundary**
(the real invokers already prove the pattern). GitHub, VS Code, Browser → additional Actuators/Harnesses.
Email, Discord, Slack → **Channel Adapters** for Human Interaction (wrap v1's working Discord/email as
the first adapters — closes part of C3). Sequence by A0's needs: `claude` + git + one channel first.

## Phase D — Operational hardening

Identity + RBAC (also satisfies C2's approver-identity), Secrets (honor the existing `.env` single-
source spine — do **not** build a second store), Telemetry/Metrics (extend v1's metrics to Stratum 2),
Scheduling/Deployment/Monitoring/Scaling. This is entirely greenfield for the v2 tier and should follow
A0, not precede it.

---

# Final Verdict

1. **How closely does today's Nexus match the original vision?** ~35–40% for the *end-to-end, real*
   request. The cognitive middle (context→plan→execute→validate→recover→learn) is real and tested; the
   methodology layer, the hands (actuation), and the governed human surface are unbuilt, and every
   validated runtime path is a stub. It reasons; it cannot yet *act* on a real environment.

2. **Where has it improved beyond the vision?** Event-sourced determinism (INV-17 replay-as-data),
   evidence-over-self-report validation (INV-20), strict capability/provider independence, and a
   39-invariant guardrail system — all stronger than the original "run the task" ask.

3. **Where has it drifted?** Not in direction — in **stratification**: the v2 engine tier forked away
   from the running v1 product (disjoint, no migration), and the validated execution path drifted to
   permanent stubs. Prior reviews compounded this by declaring completeness that the code did not back.

4. **Which drift is acceptable?** Building deterministic engines ahead of runtime; keeping the stub as
   the CI/replay substrate; designing Actuation/HI/EI before building them — *if labeled unproven*.

5. **Which drift must be corrected?** The stub as the *only* validated path (no real actuation ever
   proven); the v1/v2 disjunction; and the over-confident "architecture complete" narrative (C4).

6. **Are any foundational architectural subsystems still missing?** **No new pillar.** The gaps are
   realization (Actuation/HI/EI/Supervision/Intent-Resolution/Policy-Engine as code), grounding
   (Repository Intelligence — a capability, C2/Phase B), identity (approver authorization — C2), and a
   real integration/migration architecture (C3). All are extensions of existing seams, not missing
   foundations.

7. **Is Architecture Freeze v1 recommended?** **Yes — APPROVED WITH CONDITIONS (C1–C4).** Freeze the
   design; provisionally-freeze the unproven frontier; add the two missing seams; author the real
   migration; and correct the record.

8. **Next engineering milestone?** **A0 — one real, governed, end-to-end actuation of the reference
   request.** It is the highest-leverage move: it converts three frozen designs into evidence, proves or
   breaks the actuation freeze, forces the v1→v2 integration seam, and moves vision alignment from
   "reasons about a stub" to "operated a real repo under governance, once, for real." Only after A0
   succeeds does broad implementation (Phases A1–D) earn its budget.

**Transition recommendation:** Nexus should **enter the implementation era** — but through a single
proving vertical (A0), not a broad build-out, and not another foundational design phase. The
architecture has earned a conditional freeze; it has **not** earned the claim that it works. Make it
work once, for real, and the freeze becomes final.
