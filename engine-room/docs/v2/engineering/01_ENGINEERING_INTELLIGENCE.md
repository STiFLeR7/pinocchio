# The Engineering Intelligence Engine

Status: Target Architecture (design only)

---

# What Engineering Intelligence is

Engineering Intelligence is a decision engine.

It takes a normalized Goal and the operational situation around it, and it produces a coherent
engineering approach.

It is the platform's answer to the question an experienced engineer answers silently before
touching a keyboard:

> "Given what is being asked and what I know about this system, how should I go about this?"

That question is not planning. Planning is the *next* step — "given the approach, what are the
concrete work packages?" Engineering Intelligence is the step before: choosing the approach the
planning happens inside.

---

# What Engineering Intelligence is NOT

Engineering Intelligence is not any existing layer, and it never assumes their responsibilities.

Engineering Intelligence is **not**:

- **Intent Resolution** — it does not parse language, resolve ambiguity, or construct the Goal. It
  *receives* the Goal (`11`).
- **Context Engineering** — it does not gather, enrich, or organize context. It decides *what
  context the work requires* (Context Objectives) and hands that to Context Engineering.
- **Planning** — it does not decompose the Goal, create Work Packages, or draw the Execution Graph.
  It sets the *approach and constraints* the plan is formed within (INV-03).
- **Execution Strategy** — it does not formalize coordination/retry/timeout policy for a plan. That
  layer is downstream of Planning; EI expresses coordination *intent*, which that layer formalizes
  (`../13`, INV-05).
- **Skill Selection** — it does not choose concrete Skills. It declares *required capabilities and
  composition intent*; Skill Selection resolves them (`05`, `../06`).
- **Runtime / Orchestration** — it does not select a runtime. It expresses *runtime preference by
  capability*; Orchestration selects (`06`, INV-37).
- **Validation** — it does not judge completion. It sets the *required rigor and evidence intent*;
  Validation decides from evidence (`07`, INV-20).
- **Reflection / Knowledge** — it does not interpret outcomes or persist understanding. It
  *consumes* persisted Knowledge read-only (INV-26).
- **Governance** — it does not evaluate policy. It *respects* policy context and *proposes* within
  it; the Policy Engine evaluates and Governance authorizes (INV-28, INV-29).

Engineering Intelligence consumes these capabilities. It coordinates them. It replaces none.

---

# Responsibilities

Engineering Intelligence is responsible for:

- **classifying the engineering work** — is this a bug fix, a feature, a refactor, an
  investigation, a migration, a research task?
- **selecting an approach** — surgical vs. exploratory, research-first, validation-first,
  refactor-safe, incremental, etc.
- **determining context objectives** — what the work needs to understand before it can proceed.
- **determining skill requirements** — which operational capabilities the approach demands, and how
  they compose.
- **determining validation rigor** — how strong the completion bar must be, and what classes of
  evidence matter.
- **expressing runtime preferences** — the capability posture a runtime must have.
- **assessing risk** — blast radius, reversibility, and the acceptable risk envelope.
- **determining the autonomy level** — how much may proceed without human approval, and where
  approval gates belong.
- **assembling all of the above into one coherent Engineering Strategy.**

Engineering Intelligence **never**:

- builds context
- creates plans or work packages
- selects concrete skills or runtimes
- executes work
- validates evidence or determines completion
- evaluates governance policy
- writes to Knowledge

---

# The interpret → strategize pipeline

Engineering Intelligence runs one internal pipeline. It is deterministic on replay (`13`).

```
Goal  (+ Repository Understanding, Knowledge, Preferences, Policy, Environment)
   │
   ▼
Work Classification            what kind of engineering work is this?
   │
   ▼
Situation Assessment           what does the repository / history / knowledge tell us?
   │
   ▼
Approach Selection             which engineering posture fits?
   │
   ▼
Facet Determination            context objectives, skill requirements, validation rigor,
   │                           runtime preferences, autonomy level, risk envelope
   ▼
Strategy Composition           assemble one coherent, internally-consistent Strategy
   │
   ▼
Engineering Strategy           (recorded as an immutable decision event — INV-17)
```

Each stage records its rationale (INV-31). The Strategy is not the *last* stage's output alone; it
is the coherent composition of all facets, checked for internal consistency (e.g., "high autonomy"
must be consistent with "low risk envelope" or an approval gate is inserted).

---

# Coherence is the point

The reason Engineering Intelligence is one engine and not seven independent decisions is
**coherence**.

A human engineer does not choose skills, then separately choose rigor, then separately choose
runtime, as if unrelated. The choices constrain one another:

- A *surgical production fix* implies **high** validation rigor, **regression** evidence, a
  **supervised** autonomy level, and a **medium-high** risk envelope — together.
- An *exploratory investigation* implies **broad** context objectives, **research** skills,
  **low** completion rigor (a report, not a deployment), **high** autonomy, and a **low** risk
  envelope — together.

If seven layers each decided independently, the combination could be incoherent (high autonomy on a
high-risk irreversible action). Engineering Intelligence exists to make these decisions *as one*.
This is the single responsibility that justifies the layer (INV-02): **producing a coherent
engineering approach.**

---

# Hard boundaries

| Engineering Intelligence | Enforced by |
|---|---|
| ✓ classifies work, selects approach | own responsibility (INV-02) |
| ✓ determines strategy facets | own responsibility |
| ✓ composes one coherent Engineering Strategy | own responsibility |
| ✓ records every decision with rationale | INV-31 |
| ✗ never builds context | Context Engineering owns it (`../03`) |
| ✗ never plans or packages work | Planning owns it (INV-03) |
| ✗ never selects concrete skills or runtimes | Skill Selection / Orchestration (INV-37) |
| ✗ never executes or validates | Execution / Validation (INV-04, INV-20) |
| ✗ never evaluates policy | Policy Engine (INV-28) |
| ✗ never writes Knowledge | Knowledge Engine (INV-25) |
| ✗ never writes a plan/step into the Goal | Goals describe outcomes (INV-08) |

---

# North Star

Engineering Intelligence turns a normalized Goal into a coherent engineering approach.

It is the platform's engineer-before-the-engineering: the judgment that decides how work should
proceed, expressed as a strategy the rest of the platform enacts.

Understanding precedes pursuit. Engineering Intelligence owns the pursuit decision.
