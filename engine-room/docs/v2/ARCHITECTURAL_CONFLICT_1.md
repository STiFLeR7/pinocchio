# ARCHITECTURAL_CONFLICT_1 — Single-episode runs persist no Knowledge

Status: Evidence-backed finding from the A0 implementation vertical. **No redesign performed**
(per the A0 rule: implementation exposing an architectural issue must be documented, not fixed).

---

## The claim

The reference benchmark's final step — *"learn from the outcome … persist operational knowledge"* —
**does not fire for a single-work-item engineering task.** The A0 run completed, validated, and
recovered, but produced **zero** durable Knowledge.

## Evidence

Real A0 run (one work item, real `claude`):
```
execution: ['completed']   validation: ['passed']   recovery: ['complete']
knowledge_item_ids: []     event_count: 73
```
Deterministic reproduction of the same single-work-item topology (StubClaudeInvoker, no network):
```
execution_outcomes: ('completed',)
reflection_candidates: ()
knowledge_item_ids: ()
```
Contrast — the existing two-work-item reference workflow (`nexus_workflows/reference.py`) *does*
persist knowledge, and its own docstring states why:

> "decomposed into **two** independent work items … enough for **Reflection to confirm a pattern**
> and propose a Knowledge Candidate"

So the behavior is a function of **episode count**, not of the real-vs-stub runtime.

## Why the architecture behaves this way (not a bug)

Reflection is designed to distill **confirmed patterns** across operational episodes (INV-25/26):
one episode is an anecdote, not a pattern. With a single Work Package there is exactly one episode,
so Reflection proposes no Knowledge Candidate, and Knowledge (correctly) persists nothing. This is
principled: it prevents the learning store from filling with unconfirmed one-offs.

The conflict is not that the engine is wrong — it is that the **benchmark expectation** ("a single
run learns and persists") and the **architecture's learning model** ("learning accrues from repeated,
confirmed episodes") disagree about *when* knowledge should appear.

## Proposed alternatives

1. **Interpret step 16 as cross-run, not within-run** (lowest cost). Knowledge accrues across many
   A0 executions sharing a `knowledge_subject`; the second run already reads the first run's lesson
   (proven by `test_knowledge_from_run_one_influences_planning_in_run_two`). Adjust the benchmark's
   wording, not the engine.
2. **Single-episode "notable outcome" lessons** (small, additive). Let Reflection emit a Candidate for
   distinguished first-occurrence outcomes (first success/first failure of a new task class) without
   requiring a second episode — a configurable threshold, not a redesign.
3. **Configurable pattern-confirmation threshold** on Reflection (episodes-to-confirm = 1..N),
   defaulting to current behavior.

## Recommendation

**Adopt (1) now; consider (2) later.** The architecture is sound — do not lower the learning bar to
satisfy a one-shot benchmark. Record that "persist operational knowledge" is a **cross-run** property
of the platform, demonstrated by the knowledge-feedback test, and leave Reflection's
pattern-confirmation discipline intact. If product needs within-run lessons for high-signal outcomes,
implement (2) as an additive, configurable extension — not a change to INV-25/26.

**Severity:** low. It does not block A0 (which validated its real effect independently of Knowledge),
does not violate an invariant, and has a zero-code mitigation (1).
