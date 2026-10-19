# Acceptance Engine -- Implementation

`nexus_knowledge/acceptance.py`. The deterministic decision function at the heart of Knowledge
(doc 05): `(candidate, SubjectState, PersistencePolicy, subject_key) -> AcceptanceDecision`. Pure,
evidence-driven, no clock, no randomness, no AI, no heuristics -- Knowledge's analogue of the
Validation rule evaluator and Recovery decision precedence.

## Inputs

- `KnowledgeCandidate` -- the advisory boundary contract (doc 02).
- `SubjectState` -- the current Item, latest `KnowledgeVersion`, the set of already-recorded
  evidence reference ids, and a `terminally_rejected` flag; the Engine reads this and nothing else.
- `PersistencePolicy` -- pure data (doc 04).

## The fixed, total precedence

```
0. terminal block        subject terminally rejected           -> REJECT (rejection_terminal)
1. provenance & evidence  (INV-24 -- the recommendation is never enough)
     evidence count < minimum_evidence                         -> REJECT (insufficient_evidence)
     require_validated_provenance & any ref not validated      -> REJECT (provenance_not_validated)
2. eligibility (policy thresholds)
     confidence < minimum_confidence                           -> REJECT (below_minimum_confidence)
     kind not in accepted_kinds                                -> REJECT (kind_not_accepted)
3. subject-key resolution
     no existing Item                                          -> ACCEPT_CREATE (version 1)
4. duplicate / evolution (duplicate_strategy)
     strategy = reject_as_duplicate                            -> REJECT (duplicate)
     no new evidence AND statement unchanged                   -> REJECT (duplicate)
     statement changed (and not forced-merge)                  -> ACCEPT_EVOLVE (new version)
     otherwise (corroboration)                                 -> MERGE (accumulate + promote)
```

Every path terminates in exactly one outcome and records a rationale trace (`step: outcome --
reason`) plus the policy version (INV-31). `AcceptanceDecision` also carries
`confidence_from/to`, `evidence_added`, and `from/to_version` so the caller can build the version
and events without re-deriving anything.

## Validated provenance, without importing Validation

Step 1 must decide whether evidence "resolves to a validated outcome" while
`nexus_knowledge` imports no upstream layer. It does so **structurally**: an evidence reference is
validated iff its `target_type` is in `VALIDATED_PROVENANCE_TARGET_TYPES` (`validation_report`,
`evidence`, `observation`). A bare `execution_result` reference is *not* validated -- so a candidate
whose only support is raw execution output is rejected, exactly as doc 05 requires. This is the same
"trust the evidence, not the claim" discipline Validation applies to runtime self-reports (INV-20).

## Confidence promotion

Confidence advances deterministically along the earned `ConfidenceLadder` via
`PersistencePolicy.promoted_confidence(asserted, cumulative_evidence_count)`: the stronger of the
asserted level and the count-derived level (`confidence_for`: 1 -> Experimental, 2 -> Observed,
3-4 -> Validated, >=5 -> Proven). Promotion can only *raise* confidence; contradiction drives
deprecation/supersession instead of a silent downgrade (doc 10). With `confidence_promotion=False`
the Item holds exactly the asserted level.

## Never accept on recommendation alone

Steps 1-2 exist specifically to enforce the program rule: a candidate clears policy on *its own*
provenance and evidence before any create/evolve/merge is considered. Reflection's confidence is an
*input* to eligibility, never a substitute for it. `test_acceptance.py` exercises every reject
reason and every accept/evolve/merge branch.
