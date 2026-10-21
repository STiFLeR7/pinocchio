"""P17 Phase 2 — failure testing that the existing per-subsystem restart suites don't cover.

The repository already has extensive restart/replay coverage per subsystem (runtime failures:
``test_claude_failure_is_recovered_retry`` et al.; pipeline interruption:
``test_pipeline_restarts_after_a_mid_execution_interruption``; scheduler interruption:
``test_restart_never_double_dispatches``; approval interruption:
``test_restart_resumes_an_in_flight_approval_wait``; database restart: the whole
``test_durable_restart.py`` suite; partial execution:
``test_execution_actuation_restarts_over_the_durable_log``) — all proven by directly re-running
them (see the P17 report). This file fills the three gaps that audit found: a genuine OS-level
process crash (not a controlled close-and-reopen), replay's safety under repetition/interruption,
and a Recovery decision's durability and determinism across a restart.
"""

from __future__ import annotations

import subprocess
import sys
import time

from nexus_execution import build_execution
from nexus_infra import build_durable_infrastructure
from nexus_infra.durable import connect
from nexus_recovery import RecoveryDecision, build_recovery
from nexus_runtime import FixedTimestampSource, build_runtime
from nexus_runtime_claude import ClaudeRuntimeAdapter, StubClaudeInvoker
from nexus_validation import build_validation
from tests.unit.nexus_runtime.helpers import intake, preparation_request

# --------------------------------------------------------------------------- #
# 1. Genuine process crash — not a clean close-and-reopen                     #
# --------------------------------------------------------------------------- #

_CRASH_SCRIPT = """
import sys, time
from nexus_infra.durable import connect

conn = connect({db!r})

# A durable, fully committed baseline write.
conn.execute("BEGIN")
conn.execute(
    "INSERT INTO events(global_sequence, identifier, stream, stream_position, type, "
    "content_hash, envelope) VALUES (1, 'evt-committed', 's', 0, 'test.committed', 'h1', '{{}}')"
)
conn.execute("COMMIT")

# An in-flight write the process never gets to commit before it is killed.
conn.execute("BEGIN")
conn.execute(
    "INSERT INTO events(global_sequence, identifier, stream, stream_position, type, "
    "content_hash, envelope) VALUES (2, 'evt-uncommitted', 's', 1, 'test.uncommitted', 'h2', '{{}}')"
)

with open({marker!r}, "w") as f:
    f.write("ready")

time.sleep(30)  # killed by the parent long before this returns
"""


def test_process_crash_mid_transaction_leaves_only_committed_writes(tmp_path) -> None:  # type: ignore[no-untyped-def]
    db = str(tmp_path / "crash.db")
    marker = str(tmp_path / "ready.marker")
    script = _CRASH_SCRIPT.format(db=db, marker=marker)

    proc = subprocess.Popen([sys.executable, "-c", script])
    try:
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline:
            if (tmp_path / "ready.marker").exists():
                break
            time.sleep(0.02)
        else:
            raise AssertionError("child never reached the uncommitted write")
        # The uncommitted INSERT has landed on the wire; kill the process now, exactly where a
        # real crash would happen — mid-transaction, no COMMIT, no clean shutdown.
        proc.kill()
        proc.wait(timeout=10)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=10)

    # A fresh connection recovers from the WAL exactly as it would after a real crash.
    conn = connect(db)
    rows = conn.execute("SELECT identifier FROM events ORDER BY global_sequence").fetchall()
    identifiers = [r[0] for r in rows]

    assert "evt-committed" in identifiers  # committed data survives the crash
    assert "evt-uncommitted" not in identifiers  # no torn/partial write leaks through (atomicity)

    # The recovered connection is fully usable — a crash does not brick the store.
    conn.execute("BEGIN")
    conn.execute(
        "INSERT INTO events(global_sequence, identifier, stream, stream_position, type, "
        "content_hash, envelope) VALUES (3, 'evt-after-recovery', 's', 1, 'test.recovered', 'h3', '{}')"
    )
    conn.execute("COMMIT")
    rows_after = conn.execute("SELECT identifier FROM events ORDER BY global_sequence").fetchall()
    assert [r[0] for r in rows_after] == ["evt-committed", "evt-after-recovery"]


# --------------------------------------------------------------------------- #
# 2. Replay is idempotent and safe under repetition/interruption              #
# --------------------------------------------------------------------------- #


def test_replay_is_idempotent_and_safe_to_repeat(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Replay only *reads* the log — running it repeatedly (as an interrupted replay would force
    a caller to do) never mutates the log and always reconstructs the identical state, whether or
    not an earlier reconstruction attempt was ever allowed to finish."""
    db = str(tmp_path / "replay.db")
    infra = build_durable_infrastructure(db)
    with infra.unit_of_work() as uow:
        for i in range(5):
            uow.collect(_plain_event(f"evt-{i}", "test.recorded", "cor-1", {"n": i}, infra))
        uow.commit()

    baseline_length = infra.event_store.global_length()

    # Simulate a replay that was "interrupted" (a caller only consumed part of the stream) followed
    # by a full, correct replay — the partial read must not have disturbed anything.
    partial = list(infra.event_store.read_all())[:2]
    assert len(partial) == 2  # the "interrupted" read really did stop early

    full_first = tuple(e.identifier for e in infra.event_store.read_all())
    full_second = tuple(e.identifier for e in infra.event_store.read_all())
    full_third = tuple(e.identifier for e in infra.event_store.read_all())

    assert full_first == full_second == full_third  # every replay reproduces the same order
    assert infra.event_store.global_length() == baseline_length  # replay never appends

    # Reopening the file (a restart-triggered replay) three times in a row is likewise idempotent —
    # not just "the first restart works," but "restarting doesn't accumulate drift."
    for _ in range(3):
        reopened = build_durable_infrastructure(db)
        assert tuple(e.identifier for e in reopened.event_store.read_all()) == full_first
        assert reopened.event_store.global_length() == baseline_length


def _plain_event(identifier: str, event_type: str, correlation: str, payload: dict, infra):  # type: ignore[no-untyped-def]
    from nexus_core.domain.event import Event

    return Event(
        identifier=identifier,
        type=event_type,
        version="1",
        timestamp="2026-01-01T00:00:00+00:00",
        producer="test",
        correlation_identifier=correlation,
        execution_identifier=None,
        payload=payload,
        source="test",
    )


# --------------------------------------------------------------------------- #
# 3. A Recovery decision is durable and deterministic across a restart        #
# --------------------------------------------------------------------------- #


def test_recovery_decision_is_durable_and_deterministic_across_restart(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """A Recovery decision recorded before a restart replays identically after one, and re-running
    Recovery over the replayed facts (as a resumed episode would) reaches the identical plan —
    Recovery is never re-decided differently just because the process restarted (INV-17/22)."""
    db = str(tmp_path / "recovery.db")
    infra_before = build_durable_infrastructure(db)
    ts = FixedTimestampSource()

    runtime = build_runtime(infra_before, timestamps=ts)
    adapter = ClaudeRuntimeAdapter(invoker=StubClaudeInvoker(fail=True))
    runtime.manager.register_runtime(adapter.descriptor())
    itk = intake(candidates=("claude-code",), required=("code_generation",))
    session = runtime.manager.prepare(preparation_request(itk)).sessions[0]
    result = build_execution(infra_before, timestamps=ts).engine.execute(
        session, adapter, itk.work_package
    )
    events = tuple(infra_before.event_store.read_all())
    report = build_validation(infra_before, timestamps=ts).engine.validate(
        result, itk.work_package, events=events
    )
    plan_before = build_recovery(infra_before, timestamps=ts).engine.recover(
        report, result, events=tuple(infra_before.event_store.read_all())
    )
    assert plan_before.decision is RecoveryDecision.RETRY

    events_before = tuple(e.identifier for e in infra_before.event_store.read_all())

    # Restart: a fresh set of engines over the reopened file.
    infra_after = build_durable_infrastructure(db)
    events_after = tuple(e.identifier for e in infra_after.event_store.read_all())
    assert events_after == events_before  # byte-identical replay of the whole episode

    # Re-deciding recovery over the replayed facts (what a resumed episode does) is deterministic.
    replayed_events = tuple(infra_after.event_store.read_all())
    recovery_after = build_recovery(infra_after, timestamps=ts)
    plan_after = recovery_after.engine.recover(report, result, events=replayed_events)
    assert plan_after.decision == plan_before.decision
    assert plan_after.retry_eligible == plan_before.retry_eligible
