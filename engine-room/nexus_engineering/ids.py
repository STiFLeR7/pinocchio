"""Deterministic identifier derivation for Engineering Strategies and their events.

Every id is a pure function of the fact it names — the reasoning inputs digest and the reasoner
version — so identical inputs reproduce an identical Strategy id (idempotent, replayable;
INV-16/INV-17). Reasoning happens once; the id lets replay recognize the *same* decision.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nexus_core.contracts.base import Struct
from nexus_infra import content_hash

if TYPE_CHECKING:
    from nexus_engineering.model import ReasoningInputs


def _inputs_digest(inputs: ReasoningInputs, reasoner_version: str) -> str:
    return content_hash({"reasoner": reasoner_version, "inputs": inputs.normalized()})[:16]


def strategy_id(inputs: ReasoningInputs, reasoner_version: str) -> str:
    """A content-addressed id for one Engineering Strategy (idempotent on identical inputs)."""
    return f"es-{inputs.goal.identity}-{_inputs_digest(inputs, reasoner_version)}"


def strategized_event_id(correlation_identifier: str, payload: Struct) -> str:
    """A correlation-scoped, content-addressed id for one ``engineering.strategized`` fact."""
    return f"evt-{correlation_identifier}-eng-{content_hash(payload)[:16]}"
