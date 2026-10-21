"""04 - Runtime Selection: the same Goal, run against a different runtime adapter.

Every runtime adapter (Claude, Gemini, Shell) implements the same `RuntimeAdapter` protocol
(`nexus_execution.adapter`), so the platform above the adapter layer never branches on
provider identity. This example proves it directly: it swaps the pipeline's default adapter
(Claude) for the Shell adapter via `build_constitutional_pipeline`'s `adapter_factory` seam -
the same seam production code uses - and runs the identical reference Goal unchanged.

See README.md in this directory for the full walkthrough.
"""

from __future__ import annotations

import sys

from nexus_infra import build_infrastructure
from nexus_runtime_shell import ShellRuntimeAdapter, StubShellInvoker
from nexus_workflows.spine import build_constitutional_pipeline, spine_reference_request
from nexus_workflows.spine.model import SpineRequest


def _shell_adapter_factory(request: SpineRequest) -> ShellRuntimeAdapter:
    """Route every actuation to the shell runtime instead of the default (Claude)."""
    return ShellRuntimeAdapter(invoker=StubShellInvoker(fail=request.fail))


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")

    infra = build_infrastructure()

    # The only line that differs from 01-hello-nexus: a different adapter_factory.
    pipeline = build_constitutional_pipeline(infra, adapter_factory=_shell_adapter_factory)

    request = spine_reference_request(run="runtime-selection")
    run = pipeline.coordinator.run(request)

    print("Runtime adapter used: shell (nexus_runtime_shell.ShellRuntimeAdapter)")
    print(f"status:          {run.status.value}")
    print(f"succeeded:       {run.succeeded}")
    print(f"execution outcomes: {run.execution_outcomes}")
    print()
    print("Swap `_shell_adapter_factory` back to nothing (the default) and this example")
    print("becomes identical to 01-hello-nexus, which runs the same Goal against Claude.")
    print("Nothing above the adapter layer - Orchestration, Harness, the Runtime Manager's")
    print("matching/allocation logic, Validation, Recovery - changed at all.")


if __name__ == "__main__":
    main()
