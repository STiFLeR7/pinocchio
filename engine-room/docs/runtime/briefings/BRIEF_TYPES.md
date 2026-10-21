# Brief Types (Milestone 2)

Every supported briefing is **configuration**, not code. A `BriefType` declares *what* to brief —
a title, subject, goal outcome, Knowledge subject, and an ordered tuple of `BriefSection`s — and
nothing about *how* to produce it. All four products run the same code path
(`BriefingCoordinator.generate`); there is no hardcoded per-type workflow.

## The `BriefType` contract

```python
@dataclass(frozen=True, slots=True)
class BriefType:
    key: str                          # stable identifier, e.g. "operational-digest"
    title: str                        # human title, e.g. "Morning Operational Digest"
    subject: str                      # what is being briefed
    outcome: str                      # the Goal outcome Planning receives
    knowledge_subject: str            # the Knowledge subject learning attaches to (M5)
    sections: tuple[BriefSection, ...]  # the declared sections → Planning work items
    corpus_key: str                   # the context fragment / scope corpus
    scope_terms: tuple[str, ...]      # the Goal scope
```

Each `BriefSection` (`key`, `heading`, `objective_template`) becomes exactly one `WorkItemSpec`
requiring the abstract `code_generation` capability every runtime advertises — so any briefing
section is eligible on Claude, Gemini, or Shell without an adapter change.

## The supported catalogue

| Product | `key` | Sections |
|---|---|---|
| **Morning Operational Digest** (default) | `operational-digest` | survey-signals · summarize-health · highlight-incidents · compose-digest |
| **Research Brief** | `research-brief` | gather-sources · summarize-evidence · compare-findings · generate-briefing |
| **Architecture Brief** | `architecture-brief` | survey-components · assess-decisions · identify-risks · compose-architecture |
| **Project Status Brief** | `project-brief` | collect-status · assess-progress · surface-blockers · compose-project |

`BRIEF_CATALOG` maps each `key` to its `BriefType`, and `brief_type(key)` resolves one (raising
`KeyError` on an unknown product). The Morning Operational Digest — the mission's flagship — is the
default when `generate()` is called without a type.

## Adding a product

A new briefing is a new `BriefType` value: give it sections and register it in the catalogue. No
coordinator, composer, renderer, or engine change is required — the composer projects whatever
sections ran, and the renderers format whatever the composer produced. That is the whole point of
the configuration-driven design: the platform already knows how to plan, execute, validate, recover
from, reflect on, and learn from any declared work; a brief type just declares the work.
