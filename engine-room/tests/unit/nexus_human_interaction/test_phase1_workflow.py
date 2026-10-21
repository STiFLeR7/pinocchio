from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from nexus_human_interaction import build_human_interaction, reference_operator_request
from nexus_human_interaction.facade import _translate
from nexus_infra import (
    DuplicateEventError,
    build_durable_infrastructure,
    build_infrastructure,
)
from nexus_runtime.events import SystemTimestampSource
from nexus_workflows.spine import build_constitutional_pipeline

_REPO_ROOT = Path(__file__).resolve().parents[3]


class AdvancingClock:
    def __init__(self) -> None:
        self._time = datetime(2026, 1, 1, tzinfo=UTC)

    def now(self) -> str:
        value = self._time.isoformat()
        self._time += timedelta(seconds=1)
        return value


def test_clarification_is_typed_and_replayed_without_reunderstanding() -> None:
    infra = build_infrastructure()
    context = build_human_interaction(infra, timestamps=AdvancingClock(), learning=False)
    request = replace(reference_operator_request(run="needs-clarification"), request_text="help me")

    first = context.facade.submit(request)
    again = context.facade.restart(request)

    assert first.status == "paused"
    assert first.clarification_requests
    assert first.clarification_requests == again.clarification_requests
    assert sum(event.type == "intent.resolved" for event in infra.event_store.read_all()) == 1


def test_coordinator_resume_reemission_ignores_only_timestamp() -> None:
    infra = build_infrastructure()
    pipeline = build_constitutional_pipeline(infra, timestamps=AdvancingClock()).coordinator
    request = reference_operator_request(run="idempotency")
    payload = {"stage": "actuation"}

    spine_request = _translate(request)
    pipeline._emit(request=spine_request, event_type="pipeline.resumed", payload=payload)
    size = len(tuple(infra.event_store.read_all()))
    pipeline._emit(request=spine_request, event_type="pipeline.resumed", payload=payload)
    assert len(tuple(infra.event_store.read_all())) == size

    with pytest.raises(DuplicateEventError):
        pipeline._emit(
            request=replace(spine_request, correlation_identifier="different-correlation"),
            event_type="pipeline.resumed",
            payload=payload,
        )


def test_reused_identity_cannot_silently_change_request_text() -> None:
    infra = build_infrastructure()
    context = build_human_interaction(infra, timestamps=AdvancingClock(), learning=False)
    request = replace(reference_operator_request(run="identity-reuse"), request_text="help me")
    context.facade.submit(request)

    with pytest.raises(ValueError, match="already used for different text"):
        context.facade.restart(replace(request, request_text="write a summary"))


def test_completed_restart_returns_recorded_result_without_replaying_owners() -> None:
    infra = build_infrastructure()
    context = build_human_interaction(infra, timestamps=AdvancingClock(), learning=False)
    request = reference_operator_request(run="completed-replay")
    first = context.facade.submit(request)
    count = len(tuple(infra.event_store.read_all()))

    again = context.facade.restart(request)

    assert first.status == again.status == "completed"
    assert again.execution_status == first.execution_status
    assert again.progress == first.progress
    assert len(tuple(infra.event_store.read_all())) == count


def test_denied_approval_never_dispatches_runtime() -> None:
    infra = build_infrastructure()
    context = build_human_interaction(infra, timestamps=AdvancingClock(), learning=False)
    request = reference_operator_request(run="denied-no-dispatch", gated=("draft", "review"))
    paused = context.facade.submit(request)
    decision = context.facade.deny(request, paused.pending_approvals[0].node, decided_by="test")

    assert not decision.resumed
    assert context.facade.status(request.identity).status == "paused"
    assert not any(
        event.producer == "runtime" and event.type == "runtime.artifact_emitted"
        for event in infra.event_store.read_all()
    )


def test_approval_resumes_once_across_processes_with_system_clock(tmp_path) -> None:
    db = tmp_path / "nexus.sqlite"
    artifacts = tmp_path / "artifacts"
    run_id = "phase1-cross-process"
    infra = build_durable_infrastructure(str(db))

    from nexus_runtime_llm import LLMRuntimeAdapter
    from nexus_runtime_llm.invoker import StubLLMInvoker

    initial = build_human_interaction(
        infra,
        timestamps=SystemTimestampSource(),
        learning=False,
        adapter_factory=lambda _request: LLMRuntimeAdapter(
            invoker=StubLLMInvoker(), working_dir=str(artifacts)
        ),
    )
    request = reference_operator_request(run=run_id, gated=("draft", "review"))
    paused = initial.facade.submit(request)
    assert paused.awaiting_approval
    assert not tuple(artifacts.glob("*"))
    infra.event_store._conn.close()

    child = r"""
import json, sys
from pathlib import Path
from nexus_human_interaction import build_human_interaction, reference_operator_request
from nexus_infra import build_durable_infrastructure
from nexus_runtime.events import SystemTimestampSource
from nexus_runtime_llm import LLMRuntimeAdapter
from nexus_runtime_llm.invoker import StubLLMInvoker

db, artifacts, run_id = sys.argv[1:]
infra = build_durable_infrastructure(db)
context = build_human_interaction(
    infra, timestamps=SystemTimestampSource(), learning=False,
    adapter_factory=lambda _: LLMRuntimeAdapter(invoker=StubLLMInvoker(), working_dir=artifacts),
)
request = reference_operator_request(run=run_id, gated=("draft", "review"))
for gate in context.facade.pending_approvals(request.identity):
    decision = context.facade.approve(request, gate.node, decided_by="test")
events = tuple(infra.event_store.read_all())
runtime = [
    e for e in events
    if e.producer == "runtime"
    and e.type == "runtime.artifact_emitted"
    and e.correlation_identifier == request.correlation_identifier
    and str(e.payload.get("artifact", "")).endswith("response.md")
]
answers = [Path(artifacts, str(e.payload["artifact"])).read_text(encoding="utf-8").strip() for e in runtime]
print(json.dumps({"status": decision.pipeline_status, "artifact_count": len(runtime), "readable": all(answers), "approval_events": sum(e.type == "approval.approved" for e in events)}))
infra.event_store._conn.close()
"""
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(filter(None, (str(_REPO_ROOT), env.get("PYTHONPATH", ""))))
    result = subprocess.run(
        [sys.executable, "-c", child, str(db), str(artifacts), run_id],
        cwd=str(_REPO_ROOT),
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout.strip().splitlines()[-1])
    assert summary == {
        "status": "completed",
        "artifact_count": 2,
        "readable": True,
        "approval_events": 2,
    }
