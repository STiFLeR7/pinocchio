"""Deterministic identifier derivation for estimates and estimation events.

Every id is a pure function of the fact it names — the subject, the estimate kind, the model
version, and the signals — so an identical estimation reproduces identical ids (idempotent,
replayable; INV-16/INV-17). The ``est-`` / ``er-`` / ``mig``-style markers namespace the
subsystem in the shared, correlated store.
"""

from __future__ import annotations

from collections.abc import Mapping

from nexus_core.contracts.base import Struct
from nexus_estimation.vocabulary import EstimateKind
from nexus_infra import content_hash


def _signals_digest(model_version: str, signals: Mapping[str, float]) -> str:
    payload = {"model": model_version, "signals": {name: signals[name] for name in sorted(signals)}}
    return content_hash(payload)[:16]


def estimate_id(
    subject: str, kind: EstimateKind, model_version: str, signals: Mapping[str, float]
) -> str:
    """A content-addressed id for one estimate of ``kind`` (idempotent on identical inputs)."""
    return f"est-{kind.value}-{subject}-{_signals_digest(model_version, signals)}"


def report_id(subject: str, model_version: str, signals: Mapping[str, float]) -> str:
    """A content-addressed id for the bundled estimation report."""
    return f"er-{subject}-{_signals_digest(model_version, signals)}"


def estimated_event_id(correlation_identifier: str, payload: Struct) -> str:
    """A correlation-scoped, content-addressed id for one ``estimation.estimated`` fact."""
    return f"evt-{correlation_identifier}-est-{content_hash(payload)[:16]}"
