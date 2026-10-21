"""P17 Phase 4 — scale validation (observed limits, not synthetic ceilings).

Companion to ``scripts/p17_benchmark.py``. Covers: many concurrent pipeline sessions, many scheduled
jobs (extends Phase 3's finding), many approvals, a large execution graph, a large knowledge store,
and replay/restart at a larger event-log scale. Run:
``.venv/Scripts/python.exe scripts/p17_scale.py``.
"""

from __future__ import annotations

import shutil
import tempfile
import time
from pathlib import Path

from nexus_approval import build_approval_exchange
from nexus_core.contracts.base import Reference
from nexus_core.contracts.enums import ConfidenceLadder, KnowledgeType
from nexus_core.domain.event import Event
from nexus_infra import InMemoryObservability, build_durable_infrastructure, build_infrastructure
from nexus_knowledge.candidate import KnowledgeCandidate
from nexus_knowledge.composition import build_knowledge
from nexus_operations import build_operations
from nexus_runtime.events import FixedTimestampSource
from nexus_scheduler import build_scheduler
from nexus_scheduler.model import AutonomyMode, ScheduleTrigger
from nexus_workflows.spine import build_constitutional_pipeline
from nexus_workflows.spine.reference import spine_reference_request

RESULTS: list[tuple[str, str]] = []


def report(label: str, value: str) -> None:
    RESULTS.append((label, value))
    print(f"{label:<70} {value}")


# --------------------------------------------------------------------------- #
# 1. Many concurrent pipeline sessions (one shared durable infra)             #
# --------------------------------------------------------------------------- #


def scale_concurrent_sessions(n: int = 50) -> None:
    tmp = Path(tempfile.mkdtemp()) / "concurrent.db"
    infra = build_durable_infrastructure(str(tmp))
    ts = FixedTimestampSource()
    spine = build_constitutional_pipeline(infra, timestamps=ts)

    t0 = time.perf_counter()
    outcomes = [
        spine.coordinator.run(spine_reference_request(run=f"c{i}")).status.value for i in range(n)
    ]
    t1 = time.perf_counter()
    elapsed = t1 - t0
    completed = sum(1 for o in outcomes if o == "completed")
    report(
        f"Concurrent pipeline sessions — {n} sequential Goal->Knowledge runs, one shared durable log",
        f"{elapsed * 1000:.1f} ms total, {elapsed / n * 1000:.2f} ms/run, {completed}/{n} completed",
    )
    report(
        "Concurrent sessions — final durable log size",
        f"{infra.event_store.global_length()} events",
    )
    shutil.rmtree(tmp.parent, ignore_errors=True)


# --------------------------------------------------------------------------- #
# 2. Many scheduled jobs — extend Phase 3's tick() finding to a hard ceiling  #
# --------------------------------------------------------------------------- #


def scale_scheduler(counts: tuple[int, ...] = (500, 1000, 2000)) -> None:
    for count in counts:
        infra = build_infrastructure(observability=InMemoryObservability())
        ts = FixedTimestampSource()
        spine = build_constitutional_pipeline(infra, timestamps=ts)
        approval = build_approval_exchange(spine.coordinator, infra, now=ts.now)
        operations = build_operations(spine.coordinator, approval, infra, now=ts.now)
        sched = build_scheduler(spine, approval, operations, now=ts.now).scheduler

        for i in range(count):
            sched.schedule_goal(
                identity=f"job-{i}",
                request=spine_reference_request(run=f"s{i}"),
                trigger=ScheduleTrigger.one_time("2099-01-01T00:00:00+00:00"),
                autonomy=AutonomyMode.MANUAL,
            )

        t0 = time.perf_counter()
        sched.tick("2026-01-01T00:00:00+00:00")
        t1 = time.perf_counter()
        elapsed = t1 - t0
        report(
            f"Scheduler scale — tick() over {count} registered schedules",
            f"{elapsed * 1000:.1f} ms" + ("  <-- exceeds 1s" if elapsed > 1.0 else ""),
        )
        if elapsed > 3.0:
            report("Scheduler scale — stopping early", f"{elapsed:.1f}s exceeds 3s budget at {count}")
            break


# --------------------------------------------------------------------------- #
# 3. Many approvals — does per-operation cost grow with total approval history?#
# --------------------------------------------------------------------------- #


def scale_approvals(n: int = 40) -> None:
    infra = build_infrastructure(observability=InMemoryObservability())
    ts = FixedTimestampSource()
    spine = build_constitutional_pipeline(infra, timestamps=ts)
    approval = build_approval_exchange(spine.coordinator, infra, now=ts.now)

    per_session_ms: list[float] = []
    for i in range(n):
        request = spine_reference_request(run=f"a{i}", gated=("draft",))
        t0 = time.perf_counter()
        run = spine.coordinator.run(request)
        waiting = run.execution_state.waiting_nodes if run.execution_state is not None else ()
        approval.publish(request.pipeline_session_id, waiting)
        for node in waiting:
            approval.approve(request, node, decided_by="bench")
        t1 = time.perf_counter()
        per_session_ms.append((t1 - t0) * 1000)

    first_5 = sum(per_session_ms[:5]) / 5
    last_5 = sum(per_session_ms[-5:]) / 5
    report(
        f"Approval scale — {n} independent gated sessions (publish+approve), one shared exchange",
        f"first 5 avg {first_5:.2f} ms/session, last 5 avg {last_5:.2f} ms/session"
        f" ({last_5 / first_5:.1f}x)",
    )


# --------------------------------------------------------------------------- #
# 4. A large execution graph                                                  #
# --------------------------------------------------------------------------- #


def scale_large_execution_graph(width: int = 60) -> None:
    from tests.unit.nexus_execution.actuation.fixtures import item, make_inputs

    inputs = make_inputs(tuple(item(f"n{i}") for i in range(width)))
    from tests.unit.nexus_execution.actuation.fixtures import wired

    _infra, ctx = wired()
    t0 = time.perf_counter()
    state = ctx.actuator.actuate(inputs)
    t1 = time.perf_counter()
    report(
        f"Large execution graph — actuation traversal, {width} independent work-item nodes",
        f"{(t1 - t0) * 1000:.2f} ms, {len(state.completed_nodes)}/{width} completed",
    )


# --------------------------------------------------------------------------- #
# 5. A large knowledge store                                                  #
# --------------------------------------------------------------------------- #


def scale_knowledge_store(n: int = 500) -> None:
    infra = build_infrastructure(observability=InMemoryObservability())
    ts = FixedTimestampSource()
    bundle = build_knowledge(infra, timestamps=ts)

    t0 = time.perf_counter()
    for i in range(n):
        candidate = KnowledgeCandidate(
            identity=f"kc-{i}",
            kind=KnowledgeType.LESSON,
            subject=f"subject-{i}",
            statement=f"lesson learned #{i}",
            confidence=ConfidenceLadder.OBSERVED,
            evidence_refs=(Reference(target_type="validation_report", identifier=f"ev-{i}"),),
            originating_reflection_ref=Reference(target_type="reflection_report", identifier=f"rr-{i}"),
        )
        bundle.engine.ingest(candidate)
    t1 = time.perf_counter()
    elapsed = t1 - t0
    report(
        f"Large knowledge store — ingest {n} distinct candidates",
        f"{elapsed * 1000:.1f} ms total, {n / elapsed:.0f} ingests/sec",
    )

    t0 = time.perf_counter()
    items = bundle.repositories.items.list_all()
    t1 = time.perf_counter()
    report(
        f"Large knowledge store — list_all() over {len(items)} items",
        f"{(t1 - t0) * 1000:.2f} ms",
    )


# --------------------------------------------------------------------------- #
# 6. Replay / restart at a larger event-log scale                             #
# --------------------------------------------------------------------------- #


def _event(i: int) -> Event:
    return Event(
        identifier=f"evt-{i}",
        type="bench.recorded",
        version="1",
        timestamp="2026-01-01T00:00:00+00:00",
        producer="bench",
        correlation_identifier=f"cor-{i % 200}",
        execution_identifier=None,
        payload={"n": i},
        source="bench",
    )


def scale_replay_and_restart(n: int = 20_000) -> None:
    tmp = Path(tempfile.mkdtemp()) / "scale.db"
    infra = build_durable_infrastructure(str(tmp))
    t0 = time.perf_counter()
    batch = 500
    for start in range(0, n, batch):
        with infra.unit_of_work() as uow:
            for i in range(start, min(start + batch, n)):
                uow.collect(_event(i))
            uow.commit()
    t1 = time.perf_counter()
    report(f"Large log — append {n} events ({batch}/txn)", f"{(t1 - t0) * 1000:.0f} ms")

    t0 = time.perf_counter()
    events = list(infra.event_store.read_all())
    t1 = time.perf_counter()
    replay_elapsed = t1 - t0
    report(
        f"Replay at scale — read_all() over {len(events)} durable events",
        f"{replay_elapsed * 1000:.1f} ms, {len(events) / replay_elapsed:.0f} events/sec",
    )

    t0 = time.perf_counter()
    reopened = build_durable_infrastructure(str(tmp))
    _ = list(reopened.event_store.read_all())
    t1 = time.perf_counter()
    report(f"Restart at scale — reopen + full replay ({n} events)", f"{(t1 - t0) * 1000:.1f} ms")
    shutil.rmtree(tmp.parent, ignore_errors=True)


def main() -> None:
    print("=" * 100)
    print("P17 Phase 4 — Scale Validation")
    print("=" * 100)
    scale_concurrent_sessions()
    scale_scheduler()
    scale_approvals()
    scale_large_execution_graph()
    scale_knowledge_store()
    scale_replay_and_restart()
    print("=" * 100)
    print(f"{len(RESULTS)} measurements recorded.")


if __name__ == "__main__":
    main()
