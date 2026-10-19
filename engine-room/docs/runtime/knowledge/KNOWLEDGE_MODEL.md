# Knowledge Model -- Implementation

Implements doc 03. Two objects: the durable **Item** (the frozen core contract) and the immutable
**Version** record (a layer value object).

## Knowledge Item = `nexus_core.domain.Knowledge`

The current Item is the projection of its newest version, built by `model.build_item`:

| Item field (`Knowledge`) | Source |
|---|---|
| `identity` | the deterministic Subject Key |
| `type` | the candidate `kind` (a `KnowledgeType`) |
| `understanding` | the current version's `statement` |
| `evidence_refs` | the version's cumulative validated evidence (non-empty -> `min_length=1` holds) |
| `confidence` | the version's promoted `ConfidenceLadder` level |
| `freshness` / `status` | the lifecycle projection (see `KNOWLEDGE_LIFECYCLE.md`) |
| `candidate_ref` | the accepted candidate |
| `source` | `KnowledgeSource.REFLECTION` |
| `relationships` / `superseded_by` | supersession links (doc 10) |
| `rationale` | the Acceptance Engine's joined rationale trace |

The Item is never mutated in place; each accepted change re-projects it from a new version, and
lifecycle transitions use `model_copy(update=...)` to produce a new frozen Item.

## Knowledge Subject Key (`ids.subject_key`)

```
subject_key(kind, subject) = ki-{kind}-{normalize_subject(subject)}
```

`normalize_subject` lower-cases, splits on any run of non-alphanumeric characters, drops empties,
and **joins the tokens in sorted order**. Sorted (stable) token order is what makes equivalent
subjects collide intentionally: `"Retry Storm"` and `"storm retry"` both normalise to
`retry-storm`, so recurring candidates about one subject resolve to one Item. A symbol-only subject
slugs to `unspecified` so a key is always well-formed. No clock, no randomness (INV-16).

Version ids derive from `(subject_key, ordinal)` -> `ki-...-v0002`; event ids carry the `know`
marker (see `KNOWLEDGE_EVENTS` in the architecture / `KNOWLEDGE_INTEGRATION.md`).

## Knowledge Version (`model.KnowledgeVersion`)

The core contract has no version ordinal, so the **version chain is a layer value object** -- the
auditable history of how understanding evolved. Each record carries `{subject_key, version, kind,
subject, statement, confidence, evidence_refs (cumulative), provenance_added (this version's
candidate/pattern/reflection/evidence refs), candidate_ref, supersedes, policy_version, rationale,
correlation_identifier, timestamp}`. Versions are stored in their own repository and never mutated
or deleted; the current Item is the projection of the newest.

Provenance is by id (INV-27) and only grows across versions (INV-24): the full ledger (patterns,
reflection reports, every prior evidence ref) lives in the chain even though the Item projection
carries only the current validated evidence and the accepted candidate.
