"""Deterministic identifier derivation for Orchestration.

Every identifier an orchestration cycle produces is a pure function of the bound
Goal/Plan identities and node keys — no clock, no counter, no randomness. This is
what makes orchestration reproducible: the same Goal, Context Package, Plan,
Execution Graph, and Execution Strategy always yield the same session, queue,
dependency, approval, harness-request, runtime-request, and event identifiers.
"""

from __future__ import annotations


def session_id(goal_identity: str, version: str = "1") -> str:
    return f"session-{goal_identity}-v{version}"


def dependency_state_id(session_identity: str) -> str:
    return f"deps-{session_identity}"


def queue_state_id(session_identity: str) -> str:
    return f"queue-{session_identity}"


def approval_state_id(session_identity: str) -> str:
    return f"approvals-{session_identity}"


def harness_request_id(session_identity: str, node_identifier: str) -> str:
    return f"hreq-{session_identity}-{node_identifier}"


def runtime_request_id(session_identity: str, node_identifier: str) -> str:
    return f"rreq-{session_identity}-{node_identifier}"


def event_id(session_identity: str, kind: str, sequence: int) -> str:
    return f"evt-{session_identity}-{kind}-{sequence:04d}"


def correlation_id(goal_identity: str) -> str:
    return f"cor-{goal_identity}"
