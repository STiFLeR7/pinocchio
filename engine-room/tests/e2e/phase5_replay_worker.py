"""Fresh-process replay worker for the Phase 5 learning gate."""

from __future__ import annotations

import json
import sys
from dataclasses import replace

from nexus_infra import build_durable_infrastructure
from nexus_workflows.spine import build_constitutional_pipeline, spine_reference_request


def main() -> int:
    database, run_name = sys.argv[1:3]
    subject = sys.argv[3] if len(sys.argv) > 3 else "architecture summary generation"
    infrastructure = build_durable_infrastructure(database)
    request = replace(spine_reference_request(run=run_name), knowledge_subject=subject)
    before = tuple(infrastructure.event_store.read_all())
    before_ids = {event.identifier for event in before}
    context = build_constitutional_pipeline(infrastructure)
    replay = context.coordinator.run(request)
    after = tuple(infrastructure.event_store.read_all())
    print(
        json.dumps(
            {
                "status": replay.status.value,
                "items": [
                    item.model_dump(mode="json") for item in context.coordinator.inspect_knowledge()
                ],
                "selection": list(replay.knowledge_grounding.selected_ids)
                if replay.knowledge_grounding
                else [],
                "context_refs": [
                    [
                        record["identifier"]
                        for record in event.payload.get("selected", [])
                        if record.get("artifact_type") == "knowledge"
                    ]
                    for event in after
                    if event.type == "context.grounding.selected"
                    and event.correlation_identifier == f"cor-spine-arch-{run_name}"
                ],
                "before_types": [event.type for event in before],
                "after_types": [event.type for event in after],
                "before_ids": [event.identifier for event in before],
                "after_ids": [event.identifier for event in after],
                "added_event_types": [
                    event.type for event in after if event.identifier not in before_ids
                ],
                "knowledge_candidates_before": sum(
                    event.type == "knowledge.candidate_accepted" for event in before
                ),
                "knowledge_candidates_after": sum(
                    event.type == "knowledge.candidate_accepted" for event in after
                ),
                "runtime_before": sum(event.producer == "runtime" for event in before),
                "runtime_after": sum(event.producer == "runtime" for event in after),
            },
            sort_keys=True,
        )
    )
    infrastructure.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
