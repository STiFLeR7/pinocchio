# Knowledge Evolution -- Implementation

`nexus_knowledge/evolution.py`. The `EvolutionEngine` builds immutable version records for every
accepted change (doc 10). Evolution is always additive and auditable, never destructive.

## Versioning

- `create_version(candidate, decision, timestamp)` -> version 1 of a new Item (Accepted).
- `next_version(prior, candidate, decision, timestamp)` -> version N+1 for an evolve or merge.
- `supersede_version(prior, superseded, timestamp)` -> a version recording that this Item now
  supersedes another Subject Key.

Version ids are deterministic (`(subject_key, ordinal)`), so replay reproduces the exact chain.

## Evolve vs. merge

The Acceptance Engine chooses the outcome; the Evolution Engine applies it:

- **Evolve** (`ACCEPT_EVOLVE`): the statement advances (`candidate.statement`); evidence
  accumulates; confidence is the decision's promoted level.
- **Merge** (`MERGE`): the statement is unchanged (`prior.statement`); only evidence and confidence
  grow. Merging keeps one authoritative Item per subject rather than scattering near-duplicates.

## Evidence accumulation

`_accumulate(existing, added)` is additive and **deduplicated by reference id** (INV-16), holding
evidence by id only (INV-27). The accumulated count is the substrate for confidence promotion --
`test_corroborating_candidate_merges_and_promotes_confidence` drives an Item from Observed to
Validated by feeding three independent evidence references across three candidates.

## Superseding

When a candidate carries `supersedes_subject` and an Item exists for that (resolved) Subject Key,
`KnowledgeEngine._maybe_supersede` returns a reference to it, the new version records `supersedes`,
and `_emit_supersession`:

- transitions the old Item to `Freshness.SUPERSEDED` and sets its `superseded_by` to the new Item;
- adds the old Item to the new Item's `relationships`;
- emits `knowledge.item_superseded`.

Superseding differs from evolution: evolution refines one subject's Item in place (new version);
superseding links two Items where one replaces the other. The old Item is withheld from default
serving but fully retained (`test_candidate_can_supersede_a_prior_subject`).

## Provenance preservation & determinism

Across versioning, merging, and superseding, provenance only grows; nothing that justified past
understanding is discarded (the backing of INV-24). Evolution is a pure function of
`(incoming candidate, current Item + version chain, policy)`, so the same candidate sequence always
yields the same version chain, confidence trajectory, and supersession graph.
