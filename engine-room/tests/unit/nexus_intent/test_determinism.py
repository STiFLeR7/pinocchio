"""Determinism — identical requests → identical analysis; replay reconstructs understanding."""

from __future__ import annotations

from nexus_intent import DeterministicInterpreter
from nexus_intent.model import IntentAnalysis
from tests.unit.nexus_intent.fixtures import CLEAR, VAGUE, interpret, req

_INTERP = DeterministicInterpreter()


def test_identical_request_produces_identical_analysis() -> None:
    a = _INTERP.interpret(req("r1", CLEAR), now="t")
    b = _INTERP.interpret(req("r1", CLEAR), now="t")
    assert a == b
    assert a.identity == b.identity


def test_analysis_reconstructs_from_serialized_form() -> None:
    a = interpret(CLEAR)
    assert IntentAnalysis.model_validate(a.model_dump(mode="json")) == a


def test_clarification_replay_is_deterministic() -> None:
    a = _INTERP.interpret(req("r2", VAGUE), now="t")
    b = _INTERP.interpret(req("r2", VAGUE), now="t")
    assert a.clarifications == b.clarifications
    # clarifications survive a serialization round-trip (replayable)
    assert (
        IntentAnalysis.model_validate(a.model_dump(mode="json")).clarifications == a.clarifications
    )


def test_different_request_changes_the_analysis() -> None:
    a = interpret("fix the login bug in the module", "rA")
    b = interpret("research and compare databases", "rB")
    assert a.identity != b.identity
    assert a.intent.detected_domain != b.intent.detected_domain
