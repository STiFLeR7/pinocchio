"""P0 Task 3 — proof that the Approval Exchange genuinely gates a write-capable request.

Non-interactive, repeatable, and self-asserting (mirrors ``examples/07-approval-exchange``'s
Requested -> Pending -> Approved lifecycle, but driven through the new terminal front door's own
building blocks — ``nexus_human_interaction`` + the real/stub ``nexus_runtime_llm`` adapter —
instead of the bare Constitutional Pipeline). It demonstrates and *asserts*, not just prints:

1. A request that looks write-capable (``scripts.nexus_cli.looks_write_capable``) pauses at an
   approval gate before the runtime ever runs — the node is not executed.
2. Denying that gate leaves the session paused forever; the gated node never executes.
3. A second, independent request of the same shape: approving its gate resumes the exact same
   pipeline run and it reaches ``completed`` with a real answer artifact.

Run: ``uv run python scripts/demo_approval_gate.py``
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from nexus_cli import (
    ARTIFACTS_DIR,
    build_operator_request,
    looks_write_capable,
    response_text,
)

from nexus_human_interaction import build_human_interaction
from nexus_infra import build_infrastructure
from nexus_operations import build_operations
from nexus_runtime.events import SystemTimestampSource
from nexus_runtime_llm import (
    LLMRuntimeAdapter,
    build_llm_invoker,
    load_llm_provider_config,
)

WRITE_REQUEST = "commit these changes to the repository"


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    assert looks_write_capable(WRITE_REQUEST), "fixture request must be classified write-capable"

    infra = build_infrastructure()
    config = load_llm_provider_config()
    print(f"[demo] llm provider: {config.provider} (model={config.model})")

    def adapter_factory(_request: object) -> LLMRuntimeAdapter:
        return LLMRuntimeAdapter(invoker=build_llm_invoker(config), working_dir=ARTIFACTS_DIR)

    context = build_human_interaction(
        infra, timestamps=SystemTimestampSource(), adapter_factory=adapter_factory
    )
    hi = context.facade
    ops = build_operations(context.spine.coordinator, context.approval, infra)

    # -- 1: the gate pauses execution before the runtime ever runs ----------- #
    denied_id = f"demo-deny-{uuid.uuid4().hex[:8]}"
    denied_request = build_operator_request(WRITE_REQUEST, identity=denied_id)
    paused = hi.submit(denied_request)
    print(f"1. submit -> status={paused.status!r}, awaiting_approval={paused.awaiting_approval}")
    assert paused.status == "paused", "a write-capable request must pause at an approval gate"
    assert paused.awaiting_approval, "the paused response must surface the pending gate"
    assert response_text(ops, denied_request) == "", "a paused (ungranted) gate must not have run"

    # -- 2: denying leaves it paused forever; the gated node never executes -- #
    node = paused.pending_approvals[0].node
    decision = hi.deny(denied_request, node, decided_by="demo", reason="never authorized")
    print(f"2. deny(node={node!r}) -> resumed={decision.resumed}")
    assert not decision.resumed, "a denial must never resume execution"
    status_after_deny = hi.status(denied_id)
    assert status_after_deny.status == "paused", "a denied session must stay paused, not run"
    assert response_text(ops, denied_request) == "", "a denied gate must never produce an answer"
    print("   confirmed: denied node never executed, session remains paused indefinitely.")

    # -- 3: approving a second, independent request resumes it to completion - #
    approved_id = f"demo-approve-{uuid.uuid4().hex[:8]}"
    approved_request = build_operator_request(WRITE_REQUEST, identity=approved_id)
    paused2 = hi.submit(approved_request)
    assert paused2.status == "paused" and paused2.awaiting_approval
    node2 = paused2.pending_approvals[0].node
    decision2 = hi.approve(
        approved_request, node2, decided_by="demo", reason="reviewed and authorized"
    )
    print(
        f"3. approve(node={node2!r}) -> resumed={decision2.resumed}, status={decision2.pipeline_status!r}"
    )
    assert decision2.resumed, "an approval must resume the paused pipeline"
    assert decision2.pipeline_status == "completed", "the approved run must reach completion"
    answer = response_text(ops, approved_request)
    assert answer, "the approved, now-executed node must have produced a readable answer"
    print(f"   confirmed: approved node executed -> {answer!r}")

    print()
    print("PASS: the Approval Exchange genuinely enforces the gate — deny blocks forever,")
    print("approve is the only path that ever lets the gated node run.")


if __name__ == "__main__":
    main()
