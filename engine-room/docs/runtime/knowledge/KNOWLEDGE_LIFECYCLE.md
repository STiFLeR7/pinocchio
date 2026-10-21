# Knowledge Lifecycle -- Implementation

`nexus_knowledge/lifecycle.py`. Implements the doc-06 lifecycle deterministically, **projected onto
the frozen core vocabularies** rather than coining a new persisted state machine.

## The projection

The core `Knowledge` contract exposes `status` (`KnowledgeIngestionStatus`) and `freshness`
(`Freshness`) -- but no single "lifecycle" field. The layer names the doc-06 arc with
`KnowledgeLifecycle` (for events, version records, and rationale) and projects it onto the two
persisted fields with a total mapping:

| doc-06 lifecycle | `status` | `freshness` | served by default? |
|---|---|---|---|
| Accepted / Active | `ACCEPTED` | `CURRENT` | yes |
| Superseded | `ACCEPTED` | `SUPERSEDED` | no |
| Deprecated | `ACCEPTED` | `DEPRECATED` | no |
| Expired | `ACCEPTED` | `HISTORICAL` | no |
| Archived | `ACCEPTED` | `ARCHIVED` | no |
| Rejected | `REJECTED` | -- (no Item) | -- |

`freshness_for` / `status_for` are the forward projection; `lifecycle_of` recovers the doc-06 state
from a persisted Item's `(status, freshness)`. **Expired maps to `HISTORICAL`** (`Freshness` has no
`expired` member): staleness removes an Item from service while keeping it true-but-aged and
queryable, which is exactly `HISTORICAL`'s meaning; `ARCHIVED` remains the terminal retention state.
This coins no new persisted vocabulary -- every state is an existing `Freshness`/`status` value.

## Serving predicate

`is_served(item, policy)` = `freshness is CURRENT` **and** `confidence >= serving_confidence_floor`.
This realises the doc-06 Accepted -> Active distinction without an `ACTIVE` status value that the
core enum lacks: an Item is created Accepted+Current and served once it clears the floor (default
`Experimental`, i.e. served immediately). Only served Items are returned by default retrieval
(doc 09).

## Transitions

`KnowledgeEngine.deprecate` / `expire` / `archive` each `model_copy` the Item to the projected
freshness, persist it, and emit the matching `knowledge.item_*` event. Transitions of an unknown
subject, or on a repository-free engine, are no-ops returning `None`.

## Expiration maintenance (`maintain`)

`maintain(as_of)` is a deterministic freshness pass, not a background clock. It is a pure function
of `(Items, recorded version timestamps, as_of, policy.freshness_ttl_seconds)`: for each Active
Item it compares the latest version's recorded timestamp against `as_of` via `is_stale` (timestamps
as data, INV-17) and expires those past the TTL. Running it twice on the same state yields the same
transitions (`test_maintain_expires_stale_items`, `test_maintain_keeps_fresh_items`). With no TTL
configured it is a no-op.

## No destructive deletion

Every state change is an appended event and a re-projected Item; nothing is ever deleted.
"Forgetting" is a lifecycle state, so the platform can always answer *what did we believe then, and
why did it retire?*
