"""09 - Recovery: a failed execution still reaches a deterministic, governed outcome.

`SpineRequest(fail=True)` routes the default runtime's stub invoker down its failure path -
the same seam RC1/RC2's own regression tests use to prove recovery behavior, not a bespoke
failure injection invented for this example. The pipeline does NOT stop at the failure:
Validation judges the execution against evidence (deciding "failed", not trusting a runtime's
own claim), Recovery classifies that failure and decides a bounded continuation, and the
pipeline still reaches Knowledge - recording what was learned from the failure itself.

Highlights why this differs from a simple agent framework: a failure is not a crash, an
unhandled exception, or a silently dropped run - it is itself a governed, recorded outcome.

See README.md in this directory for the full walkthrough.
"""

from __future__ import annotations

import sys

from nexus_infra import build_infrastructure
from nexus_workflows.spine import build_constitutional_pipeline, spine_reference_request


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")

    infra = build_infrastructure()
    pipeline = build_constitutional_pipeline(infra)

    request = spine_reference_request(run="recovery", fail=True)
    run = pipeline.coordinator.run(request)

    print(f"pipeline status:      {run.status.value}   (still reaches Knowledge)")
    print(f"run.succeeded:        {run.succeeded}   (but this run did not succeed)")
    print(f"execution outcomes:   {run.execution_outcomes}")
    print(
        f"validation decisions: {run.validation_decisions}   (evidence-judged, not self-reported)"
    )
    print(
        f"recovery decisions:   {run.recovery_decisions}   (a deterministic, bounded continuation)"
    )
    print(f"knowledge recorded:   {bool(run.knowledge_item_ids)}   ({run.knowledge_item_ids})")

    assert run.status.value == "completed"
    assert not run.succeeded
    assert run.knowledge_item_ids, "even a failed run records what was learned"

    print()
    print("Compare this to 01-hello-nexus: same pipeline, same call, only `fail=True` differs.")
    print("Nothing crashed, nothing was silently dropped, and the platform still knows exactly")
    print("what happened and what it decided to do about it.")


if __name__ == "__main__":
    main()
