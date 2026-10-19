"""05 - Memory (Knowledge): reading back what a completed run durably remembered.

A completed run's Reflection stage proposes Knowledge Candidates; the Knowledge Engine judges
each against a Persistence Policy and, if accepted, creates or evolves a durable Knowledge Item.
This example passes in its own `KnowledgeRepositories` (the same composition-root seam
production code uses) so it can read the Item straight back out after the run, by identity -
not by re-deriving it, and not by inventing a query API the platform doesn't have.

See README.md in this directory for the full walkthrough.
"""

from __future__ import annotations

import sys

from nexus_infra import build_infrastructure
from nexus_knowledge import build_knowledge_repositories
from nexus_workflows.spine import build_constitutional_pipeline, spine_reference_request


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")

    infra = build_infrastructure()
    knowledge_repositories = build_knowledge_repositories()
    pipeline = build_constitutional_pipeline(infra, knowledge_repositories=knowledge_repositories)

    request = spine_reference_request(run="memory")
    run = pipeline.coordinator.run(request)

    print(f"knowledge item ids recorded this run: {run.knowledge_item_ids}")
    print()

    for item_id in run.knowledge_item_ids:
        item = knowledge_repositories.items.get(item_id)
        assert item is not None, "recorded id must be readable back from the same repository"
        print(f"-- {item_id} --")
        print(f"  type:          {item.type.value}")
        print(f"  understanding: {item.understanding}")
        print(f"  confidence:    {item.confidence.value}")
        print(f"  freshness:     {item.freshness.value}")
        print(f"  evidence refs: {len(item.evidence_refs)}")

    print()
    print("Run this script twice in a row against the SAME in-memory repositories object and")
    print("you would see the second run's candidate merged into this Item's version chain,")
    print("not a duplicate Item - Knowledge evolves by Subject Key, it never accumulates copies.")


if __name__ == "__main__":
    main()
