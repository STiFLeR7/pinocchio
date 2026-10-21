"""02 - First Pipeline: every constitutional stage, named, plus an Operations-plane view.

Builds on 01-hello-nexus: same real pipeline, same in-memory infrastructure, but this
time we narrate each of the nine stages explicitly and then observe the completed run
through the read-only Operations plane - a second, independent subsystem that never
drives execution, only reports on it.

See README.md in this directory for the full walkthrough.
"""

from __future__ import annotations

import sys

from nexus_approval import build_approval_exchange
from nexus_infra import build_infrastructure
from nexus_operations import build_operations
from nexus_workflows.spine import build_constitutional_pipeline, spine_reference_request


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # some platform strings use non-ASCII characters

    infra = build_infrastructure()
    pipeline = build_constitutional_pipeline(infra)

    # Operations plane: wired over the *same* pipeline and the Approval Exchange. It has
    # no way to start, stop, or influence a run - only to observe the shared durable log.
    approval = build_approval_exchange(pipeline.coordinator, infra)
    operations = build_operations(pipeline.coordinator, approval, infra)

    request = spine_reference_request(run="first-pipeline")

    print("Submitting one Goal. It will drive all nine constitutional stages in order:")
    print("  Intent -> Engineering -> Context -> Planning -> Actuation")
    print("    -> Validation -> Recovery -> Reflection -> Knowledge")
    print()

    run = pipeline.coordinator.run(request)

    print("-- Result --")
    print(f"status:            {run.status.value}")
    print(f"stages executed:   {run.executed_stages}")
    print(f"execution outcomes:{run.execution_outcomes}")
    print(f"validation:        {run.validation_decisions}")
    print(f"recovery:          {run.recovery_decisions}")
    print(f"knowledge items:   {run.knowledge_item_ids}")
    print()

    # Now ask Operations what it can see about this same session - independently, from
    # the durable log alone, not from the `run` object we already have in hand.
    session_id = request.pipeline_session_id
    summary = operations.service.session_lookup(session_id)
    print("-- Operations plane view of the same session --")
    print(f"session id:        {summary.session_id}")
    print(f"status:            {summary.status}")
    print(f"stages completed:  {summary.stages_completed}")
    print(f"pending approvals: {summary.pending_approvals}")


if __name__ == "__main__":
    main()
