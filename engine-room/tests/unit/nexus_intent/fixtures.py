"""Shared fixtures for the Intent Resolution (P6) suite."""

from __future__ import annotations

from nexus_infra import build_infrastructure
from nexus_intent import DeterministicInterpreter, IntentRequest, build_intent

_NOW = "2026-01-01T00:00:00Z"

CLEAR = "fix the failing authentication bug in the auth module"
VAGUE = "do something"

_INTERP = DeterministicInterpreter()


def req(identity: str, text: str, **kw) -> IntentRequest:
    return IntentRequest(
        identity=identity, raw_request=text, correlation_identifier=f"cor-{identity}", **kw
    )


def interpret(text: str, identity: str = "r1", **kw):
    return _INTERP.interpret(req(identity, text, **kw), now="t")


def wired(now=lambda: _NOW):
    infra = build_infrastructure()
    return infra, build_intent(infra, now=now)
