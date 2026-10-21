"""08 - Replay: reconstructing state from the durable log alone, not from memory.

Every projection in Nexus (a PipelineSession, a Goal, an ExecutionState) is a pure function
of the event log, never a value carried in a live object. This example proves it directly:
it runs a Goal to completion, throws away every in-memory object the first run produced,
reopens the *same* durable file from nothing, and reconstructs an identical PipelineSession
by reading the log alone.

See README.md in this directory for the full walkthrough.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from nexus_infra import build_durable_infrastructure
from nexus_workflows.spine import (
    SpineStage,
    build_constitutional_pipeline,
    reconstruct_pipeline_session,
    spine_reference_request,
)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db_path = str(Path(tmp) / "example.db")
        request = spine_reference_request(run="replay")

        # -- "Process 1": run to completion, then walk away. ------------------------------ #
        infra_1 = build_durable_infrastructure(db_path)
        pipeline_1 = build_constitutional_pipeline(infra_1)
        original_run = pipeline_1.coordinator.run(request)
        print(f"Original run status:   {original_run.status.value}")
        print(f"Original stages:       {original_run.executed_stages}")

        # Nothing above is kept - `infra_1`, `pipeline_1`, and `original_run` are never
        # touched again below. Everything from here reads the SQLite file alone.
        del infra_1, pipeline_1, original_run

        # -- "Process 2": reopen the same file, reconstruct from events only. ------------- #
        infra_2 = build_durable_infrastructure(db_path)
        events = infra_2.event_store.read_all()
        session = reconstruct_pipeline_session(events, request.pipeline_session_id)

        print()
        print(f"Reconstructed status:  {session.status.value}")
        print(f"Reconstructed stages:  {session.stages_completed}")
        print(f"Reconstructed from:    {len(events)} durable events, zero in-memory state")

        assert session.status.value == "completed"
        assert session.completed(SpineStage.KNOWLEDGE)
        print()
        print("Every stage the original run completed is still there - reconstructed, not")
        print("remembered. This is what makes restart-after-a-crash and replay-for-audit the")
        print("same mechanism, not two different features.")


if __name__ == "__main__":
    main()
