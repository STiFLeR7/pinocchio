"""01 - Hello Nexus: the smallest possible runnable Nexus v2 program.

Runs one Goal all the way to completion through the real Constitutional Pipeline -
the same driver `python -m nexus_scheduler` uses in production - over an in-memory
event log, using the platform's own reference Goal (the same one the test suite uses).

See README.md in this directory for the full walkthrough.
"""

from __future__ import annotations

import sys

from nexus_infra import build_infrastructure
from nexus_workflows.spine import build_constitutional_pipeline, spine_reference_request


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # some platform strings use non-ASCII characters

    # 1. Infrastructure: one in-memory, append-only event log. Every fact the pipeline
    #    records goes here; nothing is a private datastore.
    infra = build_infrastructure()

    # 2. Composition root: wires Intent, Engineering, Context, Planning, Actuation,
    #    Validation, Recovery, Reflection, and Knowledge over the shared log.
    pipeline = build_constitutional_pipeline(infra)

    # 3. A Goal, expressed as raw operator text (Intent Resolution turns this into a Goal).
    request = spine_reference_request(run="hello")

    # 4. Run it. One call drives every constitutional stage, in order, to completion.
    run = pipeline.coordinator.run(request)

    print(f"status:          {run.status.value}")
    print(f"succeeded:       {run.succeeded}")
    print(f"stages executed: {', '.join(run.executed_stages)}")
    print(f"knowledge items: {run.knowledge_item_ids}")


if __name__ == "__main__":
    main()
