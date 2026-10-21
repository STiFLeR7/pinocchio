"""Unit tests for the immutable ``Checkpoint`` domain model."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from nexus_core.contracts.base import Reference
from nexus_core.contracts.enums import CheckpointType
from nexus_core.contracts.status import CheckpointStage
from nexus_core.domain.checkpoint import Checkpoint
from nexus_core.state.transitions import MACHINES


def _valid_checkpoint() -> Checkpoint:
    return Checkpoint(
        identifier="cp-1",
        execution_identifier="exec-1",
        log_position=42,
        timestamp="2026-06-29T00:00:00Z",
        execution_state="executing",
        current_work_package=Reference(target_type="work_package", identifier="wp-1"),
        execution_graph_position=Reference(target_type="execution_graph", identifier="eg-1"),
        completed_nodes=("n1", "n2"),
        pending_nodes=("n3",),
        context_references=(Reference(target_type="context_package", identifier="ctx-1"),),
        artifacts_produced=(Reference(target_type="artifact", identifier="art-1"),),
        evidence_collected=(Reference(target_type="evidence", identifier="evd-1"),),
        correlation_identifier="corr-1",
    )


def test_construction() -> None:
    cp = _valid_checkpoint()
    assert cp.log_position == 42
    assert cp.completed_nodes == ("n1", "n2")
    assert cp.stage is None
    assert cp.parent_checkpoint is None


def test_construction_with_optionals() -> None:
    cp = Checkpoint(
        identifier="cp-2",
        execution_identifier="exec-1",
        log_position=0,
        timestamp="2026-06-29T00:00:00Z",
        execution_state="executing",
        current_work_package=Reference(target_type="work_package", identifier="wp-1"),
        execution_graph_position=Reference(target_type="execution_graph", identifier="eg-1"),
        completed_nodes=(),
        pending_nodes=(),
        context_references=(),
        artifacts_produced=(),
        evidence_collected=(),
        correlation_identifier="corr-1",
        stage=CheckpointStage.PERSISTED,
        checkpoint_type=CheckpointType.EXECUTION,
        version="v1",
    )
    assert cp.stage is CheckpointStage.PERSISTED
    assert cp.checkpoint_type is CheckpointType.EXECUTION


def test_immutable() -> None:
    cp = _valid_checkpoint()
    with pytest.raises(ValidationError):
        cp.log_position = 99  # type: ignore[misc]


def test_missing_required_raises() -> None:
    with pytest.raises(ValidationError):
        Checkpoint(  # type: ignore[call-arg]
            identifier="cp-1",
            execution_identifier="exec-1",
            log_position=42,
            timestamp="2026-06-29T00:00:00Z",
            execution_state="executing",
        )


def test_extra_forbidden() -> None:
    with pytest.raises(ValidationError):
        Checkpoint(  # type: ignore[call-arg]
            identifier="cp-1",
            execution_identifier="exec-1",
            log_position=42,
            timestamp="2026-06-29T00:00:00Z",
            execution_state="executing",
            current_work_package=Reference(target_type="work_package", identifier="wp-1"),
            execution_graph_position=Reference(target_type="execution_graph", identifier="eg-1"),
            completed_nodes=(),
            pending_nodes=(),
            context_references=(),
            artifacts_produced=(),
            evidence_collected=(),
            correlation_identifier="corr-1",
            unexpected="nope",
        )


def test_serialization_round_trip() -> None:
    cp = _valid_checkpoint()
    assert Checkpoint.model_validate(cp.model_dump()) == cp


def test_lifecycle_name() -> None:
    assert Checkpoint.LIFECYCLE_NAME == "checkpoint"
    assert Checkpoint.LIFECYCLE_NAME in MACHINES
