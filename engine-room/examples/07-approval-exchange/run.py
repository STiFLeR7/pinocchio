"""07 - Approval Exchange: a gated node pauses execution, an operator decision resumes it.

A Work Item marked `requires_approval` becomes an approval gate in the compiled plan.
Actuation runs everything up to that gate, then pauses (the pipeline reaches `PAUSED`,
not `COMPLETED`) instead of executing the gated node. The Approval Exchange is the sole
owner of what happens next: publish the pending request, record the operator's decision,
and - only on approval - resume the exact same pipeline run with that gate now authorized.

Lifecycle demonstrated: Requested -> Pending -> Approved -> Execution (resumed).

See README.md in this directory for the full walkthrough.
"""

from __future__ import annotations

import sys

from nexus_approval import build_approval_exchange
from nexus_infra import build_infrastructure
from nexus_workflows.spine import (
    SpineStatus,
    build_constitutional_pipeline,
    spine_reference_request,
)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")

    infra = build_infrastructure()
    pipeline = build_constitutional_pipeline(infra)
    exchange = build_approval_exchange(pipeline.coordinator, infra)

    # `gated=("review",)` marks the "review" work item as an approval gate.
    request = spine_reference_request(run="approval", gated=("review",))

    paused = pipeline.coordinator.run(request)
    print(f"1. First run status: {paused.status.value}")
    print(f"   waiting on gate(s): {paused.execution_state.waiting_nodes}")

    # -- Requested / Pending -------------------------------------------------------- #
    pending = exchange.publish(request.pipeline_session_id, paused.execution_state.waiting_nodes)
    print(f"2. Published {len(pending)} approval request(s):")
    for p in pending:
        print(f"   node={p.node} state={p.state.value}")

    explanation = exchange.explanation(request.pipeline_session_id, "node-review")
    print(f"3. Explanation before a decision: state={explanation.state.value}")

    # -- Approved -> resumed execution ---------------------------------------------- #
    decision = exchange.approve(request, "node-review", decided_by="alice", reason="looks correct")
    print(f"4. Decision recorded: state={decision.state.value}, resumed={decision.resumed}")
    print(f"   pipeline status after resuming: {decision.pipeline_status}")

    assert decision.pipeline_status == SpineStatus.COMPLETED.value
    print()
    print("The gated node never ran until this exact approval was recorded - had `deny()`")
    print("been called instead, the session would stay paused forever and the gated node")
    print("would never execute, by design.")


if __name__ == "__main__":
    main()
