"""Shared fixtures for the Execution History (P8) suite — a controlled, deterministic event log."""

from __future__ import annotations

from nexus_core.domain.event import Event
from nexus_history import build_history
from nexus_infra import build_infrastructure

_NOW = "2026-01-01T00:00:00Z"


def ev(
    identifier: str,
    event_type: str,
    correlation: str,
    payload: dict | None = None,
    *,
    producer: str = "runtime",
    source: str = "nexus_runtime",
) -> Event:
    """Build a canonical operational Event for seeding the log."""
    return Event(
        identifier=identifier,
        type=event_type,
        version="1",
        timestamp=_NOW,
        producer=producer,
        correlation_identifier=correlation,
        execution_identifier=None,
        payload=payload or {},
        source=source,
    )


def seed_episode(infra, correlation: str = "op-1", runtime: str = "claude") -> None:
    """Emit one realistic operational episode (runtime → validation → recovery → reflect → learn)."""
    c = correlation
    for e in (
        ev(f"{c}-rt-start", "runtime.started", c, {"runtime": runtime, "work_package": "wp-1"}),
        ev(f"{c}-rt-done", "runtime.completed", c, {"runtime": runtime}),
        ev(f"{c}-rt-art", "runtime.artifact_emitted", c, {"artifact": f"{c}-art-2"}),
        ev(
            f"{c}-rrc",
            "orchestration.runtime_request_created",
            c,
            {"runtime": runtime},
            producer="orchestration",
            source="nexus_orchestration",
        ),
        ev(
            f"{c}-wp",
            "work_package.created",
            c,
            {"work_package": "wp-1"},
            producer="planning",
            source="nexus_planning",
        ),
        ev(
            f"{c}-val",
            "validation.completed",
            c,
            {"outcome": "passed", "artifact": f"{c}-art-1"},
            producer="validation",
            source="nexus_validation",
        ),
        ev(
            f"{c}-vev",
            "validation.evidence_collected",
            c,
            {"sources": ["log"]},
            producer="validation",
            source="nexus_validation",
        ),
        ev(
            f"{c}-rec",
            "recovery.decision_created",
            c,
            {"decision": "retry"},
            producer="recovery",
            source="nexus_recovery",
        ),
        ev(
            f"{c}-rfl",
            "reflection.report_created",
            c,
            {"report": f"{c}-rep"},
            producer="reflection",
            source="nexus_reflection",
        ),
        ev(
            f"{c}-kc",
            "knowledge.candidate_received",
            c,
            {},
            producer="knowledge",
            source="nexus_knowledge",
        ),
        ev(
            f"{c}-ka",
            "knowledge.candidate_accepted",
            c,
            {"candidate": "cand-1", "subject_key": "sk-1"},
            producer="knowledge",
            source="nexus_knowledge",
        ),
        ev(
            f"{c}-ki",
            "knowledge.item_created",
            c,
            {"subject_key": "sk-1"},
            producer="knowledge",
            source="nexus_knowledge",
        ),
    ):
        infra.emit(e)


def wired(now=lambda: _NOW):
    infra = build_infrastructure()
    return infra, build_history(infra, now=now)
