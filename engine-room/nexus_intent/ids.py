"""Deterministic identifier derivation for intent analyses and their events.

Every id is a pure function of the raw request and the interpreter version, so an identical request
reproduces an identical analysis id (idempotent, replayable; INV-16/INV-17). Understanding happens
once; the id lets replay recognize the *same* understanding.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nexus_core.contracts.base import Struct
from nexus_infra import content_hash

if TYPE_CHECKING:
    from nexus_intent.model import IntentRequest


def _request_digest(request: IntentRequest, interpreter_version: str) -> str:
    return content_hash({"interpreter": interpreter_version, "request": request.normalized()})[:16]


def analysis_id(request: IntentRequest, interpreter_version: str) -> str:
    """A content-addressed id for one intent analysis (idempotent on identical requests)."""
    return f"ia-{request.identity}-{_request_digest(request, interpreter_version)}"


def resolved_event_id(correlation_identifier: str, payload: Struct) -> str:
    """A correlation-scoped, content-addressed id for one ``intent.resolved`` fact."""
    return f"evt-{correlation_identifier}-int-{content_hash(payload)[:16]}"
