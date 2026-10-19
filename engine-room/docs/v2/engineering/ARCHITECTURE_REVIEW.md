# Engineering Intelligence — Architecture Review & Ratification

Status: Design review (design only). No implementation, no ADR/contract/invariant change.

This review evaluates the Engineering Intelligence architecture (`README`, `00`–`14`) for
correctness, completeness, and readiness, and answers the ratification questions. Its purpose is to
certify that a future team can build Engineering Intelligence **without making new architectural
decisions**, and to state whether EI completes the original vision or whether fundamental subsystems
remain missing.

---

# 1. Dependency direction

**Verdict: sound and structurally enforced.**

```
Intent Resolution ──Goal (by value)──▶ Engineering Intelligence ──Strategy (read-only)──▶ downstream engines
Repository Intelligence / Knowledge / Preferences / Policy / Environment ──read-only──▶ EI
nexus_engineering → { nexus_core, nexus_infra }   (only)
```

- EI imports **no** downstream engine (not Planning, Execution, Validation) and **no** upstream
  layer's internals; it consumes the Goal and all situational inputs **by value / read-only** at its
  boundary (`02`). This matches every layer built so far (`nexus_knowledge`, `nexus_runtime` →
  `{nexus_core, nexus_infra}`).
- EI is imported by nothing upstream; downstream engines hold the Strategy read-only (`03`).
- Because EI imports no downstream engine, **no consumer can reach into EI through the Strategy** —
  the Strategy crosses the boundary as a value, exactly as Knowledge Candidates cross into the
  Knowledge Engine. INV-01 holds by construction, not convention.

---

# 2. Boundary correctness against existing layers

**Verdict: no responsibility is duplicated; every seam is one-directional.**

- **Intent Resolution (`../16`)** — EI consumes its Goal and never re-interprets intent (`11`).
  INV-02/07/08 preserved.
- **Context Engineering (`../03`)** — EI emits Context Objectives; Context gathers. No overlap.
- **Planning (`../04`)** — EI sets approach/constraints; Planning decomposes. INV-03 preserved.
- **Execution Strategy (`../13`)** — EI expresses coordination *intent*; that layer formalizes.
  INV-05 preserved.
- **Skill Selection (`../06`)** — EI declares capability requirements; Selection resolves Skills.
  INV-33 preserved.
- **Orchestration** — EI expresses runtime *preference by capability*; Orchestration selects.
  INV-37 preserved.
- **Validation (`../14`)** — EI sets rigor; Validation renders the verdict from evidence. INV-20/21
  preserved.
- **Governance / Policy** — EI proposes within a ceiling; never evaluates policy or authorizes.
  INV-28/29/30 preserved.
- **Reflection / Knowledge** — EI consumes Knowledge read-only; learns only through Reflection →
  Knowledge. INV-25/26 preserved.

The producer/enactor discipline (`03`) — EI emits *intent/preference/requirement/envelope*, never a
concrete plan, runtime, Skill, or verdict — is what makes every one of these seams safe.

---

# 3. Contract impact

**Verdict: additive only; no existing contract changes.**

- EI introduces **one new artifact**, the Engineering Strategy, with its own proposed contract (G1).
- It modifies **no** existing contract. The downstream engines already accept these decisions as
  inputs — today authored by the operator. EI moves *authorship* from human to platform; it does not
  change the engines' input contracts (`03`).
- This is the key compatibility property: **EI adds a producer, not a mutation.** Every existing
  engine keeps its contract, responsibility, and tests. "All previous engineering programs remain
  green" holds by construction, because none of their code or contracts is touched.

---

# 4. Determinism

**Verdict: preserved via the determinism seam; identical to the platform's existing pattern.**

- EI *generation* is heuristic and may use a reasoning capability (`12`).
- EI *output* is captured as an immutable decision event (INV-17); replay reproduces the downstream
  pipeline from the recorded Strategy without re-inference.
- The coherence check is a pure function of the facets (`04`); same facets → same outcome.
- This is the **same** guarantee Nexus already relies on for its highest-stakes non-determinism —
  recorded LLM execution output (INV-17). EI applies it one layer up, to a *single* decision
  recorded *once*, before any work happens. If the platform trusts recorded execution replay, it
  trusts recorded strategy replay a fortiori.

---

# 5. Governance & auditability

**Verdict: strong.**

- Every Strategy facet records rationale (INV-31); "why did the platform pursue this work this way?"
  is answerable entirely from the log.
- EI proposes autonomy/risk within a policy ceiling that fails closed (INV-28/30); Governance
  authorizes (INV-29). EI influences but never evaluates policy — the same posture as Knowledge.
- The autonomy model (`08`) keeps human authority final: every gate is a real, rejectable approval
  point; uncertainty lowers autonomy.

---

# 6. Evolution & provider independence

**Verdict: learns safely, provider-independent permanently.**

- EI is **stateless** and never self-updates (`13`); all learning lives in Knowledge/Preferences,
  written only through the governed Reflection → Knowledge path (INV-25/26). No second, ungoverned
  learning path exists.
- EI is provider-independent by construction: it reasons in capabilities (INV-32), its own reasoning
  engine is itself a swappable capability, and no facet names a provider (`06`, `13`). Provider
  independence is structural, not temporary.

---

# 7. Readiness

**Verdict: ready to implement against fixed seams.**

- Reuses the existing substrate unchanged (event log, capability model, Harness Registry,
  read-only Knowledge consumption) — no new mechanism to invent.
- Tolerates absent Repository Understanding, Knowledge, and Preferences (`02`, `09`), so a first EI
  can ship before those subsystems are deep.
- Every open item (`14`) is a named, non-blocking extension; the core needs no new architectural
  decision.

---

# Ratification questions

### 1. Can Engineering Intelligence be implemented without architectural ambiguity?
**Yes.** The subsystem, placement, inputs, outputs, the Engineering Strategy artifact and its
facets, the coherence rules, the decision flow, the determinism seam, governance, and provider
independence are all specified (`00`–`13`). Open items are explicitly deferred and non-blocking
(`14`). A team can build the core with no new architectural decision.

### 2. Does EI preserve the one-way dependency flow (INV-01/02)?
**Yes — structurally.** EI imports only `{nexus_core, nexus_infra}`, consumes all inputs by
value/read-only, and emits one read-only artifact. It duplicates no existing responsibility (§2).

### 3. Does EI preserve determinism (INV-17) and auditability (INV-31)?
**Yes.** Heuristic generation, immutable recorded output, deterministic replay (`12`); every facet
carries rationale (`13`). Same pattern as recorded execution replay.

### 4. Does EI preserve the learning invariants (INV-25/26)?
**Yes.** EI consumes Knowledge read-only and never writes it; it learns only through Reflection →
Knowledge and holds no durable state of its own (`13`). No ungoverned learning path is created.

### 5. Does EI change any existing engine, contract, ADR, or invariant?
**No.** It adds one new artifact and one new upstream subsystem, consumed additively. No existing
engine, contract, ADR, or invariant is modified (§3). Previous programs remain green by
construction.

---

# Does Engineering Intelligence complete the original vision?

**It completes the *decision* half. It does not, by itself, complete the *actuation* half.**

The original vision was Nexus becoming the orchestrator:

```
Human → understand intent → understand how I engineer → understand the repository
      → determine strategy → select skills → decide validation → runtime strategy
      → build execution objectives → Context → Planning → …
```

Engineering Intelligence supplies the missing **cognitive spine** of that chain — "understand how I
engineer → determine strategy → … → build execution objectives" — as one coherent, governed,
provider-independent decision. With EI defined, the platform has an owner for the engineering
judgment that today lives in the human who hand-authors submissions. That is the single largest
architectural gap in the *understanding* pipeline, and this design closes it.

But EI is a *decider*, not a *doer*. Two classes of subsystem remain fundamentally missing for the
vision of an orchestrator that can take the reference request end to end:

1. **Perception & grounding — Repository Intelligence (as a full subsystem).** EI's decisions are
   only as grounded as the repository facts it reads. The seam is fixed (`10`); the subsystem itself
   is deferred (`14` G2). Without it, EI strategizes against thin ground truth.

2. **Actuation & the human channel.** EI decides *how* work should proceed and *where* a human must
   approve — but the platform still needs real, supervised runtime execution with filesystem/git/tool
   actuation, and a human-interaction surface to enact the approval/clarification gates EI proposes
   (`14` G10). These are downstream of EI and outside its scope, but they are what turn a decided
   strategy into a completed, reported outcome.

So the honest architectural verdict: **Engineering Intelligence completes the platform's ability to
*decide* how engineering work should proceed — the highest-leverage missing cognition — but the
architecture is not yet complete.** The remaining fundamentals are perception (a full Repository
Intelligence subsystem) and actuation (real supervised execution plus a human-interaction channel).
With EI ratified, the *understanding* side of Nexus is architecturally whole; the *doing* side is
the next frontier.

---

# Certification

The Engineering Intelligence architecture is **internally consistent, invariant-preserving
(INV-01/02/08/17/25/26/28/29/31/32/33/37), deterministic-on-replay, auditable, provider-independent,
and complete for its defined scope**, with all frontier concerns named and deferred (`14`). It
amends no ADR, contract, or invariant, adds no code, and contradicts nothing in the frozen
architecture; it inserts one new decision layer between Intent Resolution and Context Engineering and
one new upstream subsystem (Repository Intelligence) consumed read-only.

**Recommendation: ratify and freeze the core.** A future team may build the `nexus_engineering`
subsystem directly against these documents. Proceed in parallel to scope the two named downstream
frontiers — a full Repository Intelligence subsystem and the actuation/human-interaction surface —
which complete the orchestrator vision that Engineering Intelligence makes decidable.
