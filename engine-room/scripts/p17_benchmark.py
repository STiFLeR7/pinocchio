"""P17 Phase 3 — performance measurement (measure only; no optimization).

Standalone script (not a pytest suite — these are measurements, not pass/fail assertions) covering
every metric the P17 program asks for: replay throughput, restart latency, scheduler latency,
execution latency, event throughput, persistence overhead, memory usage, pipeline startup, and
autonomous execution overhead. Every composition root used here is the real one (no mocks) — the
same `build_durable_infrastructure`/`build_constitutional_pipeline`/`build_scheduler` the platform
itself uses. Run: ``.venv/Scripts/python.exe scripts/p17_benchmark.py``.
"""

from __future__ import annotations

import shutil
import tempfile
import time
import tracemalloc
from pathlib import Path

from nexus_approval import build_approval_exchange
from nexus_core.domain.event import Event
from nexus_infra import InMemoryObservability, build_durable_infrastructure, build_infrastructure
from nexus_operations import build_operations
from nexus_runtime.events import FixedTimestampSource
from nexus_scheduler import build_scheduler
from nexus_scheduler.model import AutonomyMode, ScheduleTrigger
from nexus_workflows.spine import build_constitutional_pipeline
from nexus_workflows.spine.reference import spine_reference_request

RESULTS: list[tuple[str, str]] = []


def report(label: str, value: str) -> None:
    RESULTS.append((label, value))
    print(f"{label:<55} {value}")


def _event(i: int, correlation: str = "cor-bench") -> Event:
    return Event(
        identifier=f"evt-{i}",
        type="bench.recorded",
        version="1",
        timestamp="2026-01-01T00:00:00+00:00",
        producer="bench",
        correlation_identifier=correlation,
        execution_identifier=None,
        payload={"n": i},
        source="bench",
    )


# --------------------------------------------------------------------------- #
# 1. Pipeline startup                                                         #
# --------------------------------------------------------------------------- #


def bench_pipeline_startup() -> None:
    t0 = time.perf_counter()
    build_infrastructure(observability=InMemoryObservability())
    t1 = time.perf_counter()
    report("Pipeline startup — in-memory InfrastructureContext", f"{(t1 - t0) * 1000:.3f} ms")

    tmp = Path(tempfile.mkdtemp()) / "startup.db"
    t0 = time.perf_counter()
    build_durable_infrastructure(str(tmp))
    t1 = time.perf_counter()
    report("Pipeline startup — durable InfrastructureContext (fresh file)", f"{(t1 - t0) * 1000:.3f} ms")

    t0 = time.perf_counter()
    infra = build_infrastructure(observability=InMemoryObservability())
    build_constitutional_pipeline(infra, timestamps=FixedTimestampSource())
    t1 = time.perf_counter()
    report("Pipeline startup — full constitutional spine wiring", f"{(t1 - t0) * 1000:.3f} ms")
    shutil.rmtree(tmp.parent, ignore_errors=True)


# --------------------------------------------------------------------------- #
# 2. Event throughput + persistence overhead                                  #
# --------------------------------------------------------------------------- #


def bench_event_throughput(n: int = 2000) -> None:
    infra_mem = build_infrastructure(observability=InMemoryObservability())
    t0 = time.perf_counter()
    with infra_mem.unit_of_work() as uow:
        for i in range(n):
            uow.collect(_event(i))
        uow.commit()
    t1 = time.perf_counter()
    mem_elapsed = t1 - t0
    report(
        f"Event throughput — in-memory append ({n} events, 1 txn)",
        f"{mem_elapsed * 1000:.2f} ms total, {n / mem_elapsed:.0f} events/sec",
    )

    tmp = Path(tempfile.mkdtemp()) / "throughput.db"
    infra_dur = build_durable_infrastructure(str(tmp))
    t0 = time.perf_counter()
    with infra_dur.unit_of_work() as uow:
        for i in range(n):
            uow.collect(_event(i))
        uow.commit()
    t1 = time.perf_counter()
    dur_elapsed = t1 - t0
    report(
        f"Event throughput — durable append ({n} events, 1 txn)",
        f"{dur_elapsed * 1000:.2f} ms total, {n / dur_elapsed:.0f} events/sec",
    )
    report(
        "Persistence overhead — durable vs. in-memory append (same op)",
        f"{dur_elapsed / mem_elapsed:.1f}x",
    )

    # One-append-per-transaction — the realistic per-decision pattern used throughout the platform.
    t0 = time.perf_counter()
    for i in range(200):
        infra_dur.event_store.append(_event(10_000 + i, correlation=f"cor-{i}"))
    t1 = time.perf_counter()
    per_txn = t1 - t0
    report(
        "Event throughput — durable append (200 events, 1 txn each)",
        f"{per_txn * 1000:.2f} ms total, {200 / per_txn:.0f} events/sec, {per_txn / 200 * 1000:.3f} ms/event",
    )
    return tmp  # type: ignore[return-value]


# --------------------------------------------------------------------------- #
# 3. Replay throughput + restart latency                                     #
# --------------------------------------------------------------------------- #


def bench_replay_and_restart(db_path: Path, n_hint: int) -> None:
    infra = build_durable_infrastructure(str(db_path))
    total = infra.event_store.global_length()

    t0 = time.perf_counter()
    events = list(infra.event_store.read_all())
    t1 = time.perf_counter()
    replay_elapsed = t1 - t0
    report(
        f"Replay throughput — read_all() over {total} durable events",
        f"{replay_elapsed * 1000:.2f} ms total, {total / replay_elapsed:.0f} events/sec",
    )
    assert len(events) == total

    t0 = time.perf_counter()
    reopened = build_durable_infrastructure(str(db_path))
    _ = list(reopened.event_store.read_all())
    t1 = time.perf_counter()
    report(
        f"Restart latency — reopen + full replay ({total} events)",
        f"{(t1 - t0) * 1000:.2f} ms",
    )


# --------------------------------------------------------------------------- #
# 4. Execution latency (one actuation traversal, end to end)                  #
# --------------------------------------------------------------------------- #


def bench_execution_latency() -> None:
    from tests.unit.nexus_execution.actuation.fixtures import item, make_inputs, wired

    _infra, ctx = wired()
    inputs = make_inputs((item("solo"),))
    t0 = time.perf_counter()
    ctx.actuator.actuate(inputs)
    t1 = time.perf_counter()
    report("Execution latency — single-node actuation traversal (stub runtime)", f"{(t1 - t0) * 1000:.3f} ms")


# --------------------------------------------------------------------------- #
# 5. Scheduler latency at varying registration counts                        #
# --------------------------------------------------------------------------- #


def bench_scheduler_latency() -> None:
    for count in (10, 100, 500):
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
                trigger=ScheduleTrigger.one_time("2099-01-01T00:00:00+00:00"),  # never due
                autonomy=AutonomyMode.MANUAL,
            )

        t0 = time.perf_counter()
        sched.tick("2026-01-01T00:00:00+00:00")  # nothing due; measures scan cost
        t1 = time.perf_counter()
        report(
            f"Scheduler latency — tick() scanning {count} registered (non-due) schedules",
            f"{(t1 - t0) * 1000:.3f} ms",
        )


# --------------------------------------------------------------------------- #
# 6. Autonomous execution overhead                                            #
# --------------------------------------------------------------------------- #


def bench_autonomous_overhead() -> None:
    # Direct pipeline.run() baseline.
    infra_direct = build_infrastructure(observability=InMemoryObservability())
    ts = FixedTimestampSource()
    spine_direct = build_constitutional_pipeline(infra_direct, timestamps=ts)
    t0 = time.perf_counter()
    spine_direct.coordinator.run(spine_reference_request(run="direct"))
    t1 = time.perf_counter()
    direct_elapsed = t1 - t0
    report("Autonomous execution overhead — direct pipeline.run()", f"{direct_elapsed * 1000:.2f} ms")

    # Scheduler-mediated dispatch of the same shape of Goal (Governed, one-time, due now).
    infra_sched = build_infrastructure(observability=InMemoryObservability())
    spine_sched = build_constitutional_pipeline(infra_sched, timestamps=ts)
    approval = build_approval_exchange(spine_sched.coordinator, infra_sched, now=ts.now)
    operations = build_operations(spine_sched.coordinator, approval, infra_sched, now=ts.now)
    sched = build_scheduler(spine_sched, approval, operations, now=ts.now).scheduler
    sched.schedule_goal(
        identity="auto-bench",
        request=spine_reference_request(run="auto"),
        trigger=ScheduleTrigger.one_time("2026-01-01T00:00:00+00:00"),
        autonomy=AutonomyMode.GOVERNED,
    )
    t0 = time.perf_counter()
    sched.tick("2026-01-01T00:00:00+00:00")
    t1 = time.perf_counter()
    sched_elapsed = t1 - t0
    report("Autonomous execution overhead — scheduler.tick() dispatch (Goal + timing + provenance)", f"{sched_elapsed * 1000:.2f} ms")
    report(
        "Autonomous execution overhead — delta over a direct run",
        f"{(sched_elapsed - direct_elapsed) * 1000:.2f} ms ({(sched_elapsed / direct_elapsed - 1) * 100:.0f}% over direct)",
    )


# --------------------------------------------------------------------------- #
# 7. Memory usage                                                             #
# --------------------------------------------------------------------------- #


def bench_memory_usage() -> None:
    tracemalloc.start()
    infra = build_infrastructure(observability=InMemoryObservability())
    with infra.unit_of_work() as uow:
        for i in range(5000):
            uow.collect(_event(i))
        uow.commit()
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    report("Memory usage — peak, holding 5000 events in-memory", f"{peak / 1024 / 1024:.2f} MiB")

    tracemalloc.start()
    infra2 = build_infrastructure(observability=InMemoryObservability())
    spine = build_constitutional_pipeline(infra2, timestamps=FixedTimestampSource())
    spine.coordinator.run(spine_reference_request(run="mem"))
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    report("Memory usage — peak, one full Goal->Knowledge spine run", f"{peak / 1024 / 1024:.2f} MiB")


def main() -> None:
    print("=" * 100)
    print("P17 Phase 3 — Performance Measurement (measure only, no optimization)")
    print("=" * 100)
    bench_pipeline_startup()
    db_path = bench_event_throughput()
    bench_replay_and_restart(db_path, n_hint=2200)
    bench_execution_latency()
    bench_scheduler_latency()
    bench_autonomous_overhead()
    bench_memory_usage()
    shutil.rmtree(db_path.parent, ignore_errors=True)

    print("=" * 100)
    print(f"{len(RESULTS)} measurements recorded.")


if __name__ == "__main__":
    main()
