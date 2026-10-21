"""Engine behavior — one analysis, one recorded fact, clarifications emitted-not-handled."""

from __future__ import annotations

from nexus_intent.events import INTENT_RESOLVED
from tests.unit.nexus_intent.fixtures import CLEAR, VAGUE, req, wired


def test_resolve_produces_one_analysis_and_one_event() -> None:
    infra, ir = wired()
    analysis = ir.engine.resolve(req("r1", CLEAR))
    events = [e for e in infra.event_store.read_all() if e.type == INTENT_RESOLVED]
    assert len(events) == 1
    assert events[0].correlation_identifier == "cor-r1"
    assert events[0].payload["analysis"]["identity"] == analysis.identity
    assert events[0].payload["resolved"] is True


def test_clarifications_are_emitted_in_the_fact_not_handled() -> None:
    infra, ir = wired()
    analysis = ir.engine.resolve(req("r2", VAGUE))
    event = next(e for e in infra.event_store.read_all() if e.type == INTENT_RESOLVED)
    # requests are recorded (emitted) — Human Interaction (later) handles them.
    assert event.payload["clarifications"]  # the request ids are in the fact
    assert analysis.goal is None
    assert event.payload["goal"] is None


def test_analysis_is_persisted() -> None:
    _, ir = wired()
    analysis = ir.engine.resolve(req("r3", CLEAR))
    assert ir.repositories.analyses.get(analysis.identity) == analysis


def test_engine_records_interpreter_version() -> None:
    _, ir = wired()
    assert ir.engine.interpreter_version == "1"
    assert ir.engine.resolve(req("r4", CLEAR), persist=False).interpreter_version == "1"
