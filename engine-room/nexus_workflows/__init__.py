"""``nexus_workflows`` -- end-to-end operational workflow integration (Capability Program 1).

This package proves the Nexus control plane functions as **one coherent system**: it composes the
ten independently-built engines into a complete execution flow, using only their existing public
APIs, redesigning nothing::

    Goal -> Context -> Plan -> Work Packages -> Execution Graph -> Harness -> Runtime
         -> Execution -> Validation -> Recovery -> Reflection -> Knowledge

It introduces no new architecture, engine, contract, ADR, or invariant. It contains three
orchestration primitives (Milestone 1) -- :class:`PipelineBuilder` (wire every engine over one
shared infrastructure + clock), :class:`WorkflowCoordinator` (drive the engines in order for one
request, recording a cross-layer timeline), and :class:`PipelineExecutor` (run + replay from the
event log) -- plus a deterministic reference workflow and the one sanctioned Harness->Runtime
projection.

Dependency direction: ``nexus_workflows`` sits above every engine (it is the integration boundary,
so it may import them all) and is imported by nothing. It preserves INV-26 structurally: the
learning loop reaches Planning only through a read-only Knowledge query, never through Reflection.
"""

from __future__ import annotations

from nexus_workflows.coordinator import WorkflowCoordinator, WorkflowRun
from nexus_workflows.executor import (
    PipelineExecutor,
    ReplayStage,
    ReplayTimeline,
    reconstruct,
)
from nexus_workflows.pipeline import Pipeline, PipelineBuilder
from nexus_workflows.projection import project_intake
from nexus_workflows.reference import (
    KNOWLEDGE_SUBJECT,
    reference_request,
)
from nexus_workflows.request import WorkflowRequest
from nexus_workflows.timeline import (
    StageRecord,
    TimelineRecorder,
    WorkflowTimeline,
)

__version__ = "2.5.0"

__all__ = [
    "KNOWLEDGE_SUBJECT",
    "Pipeline",
    "PipelineBuilder",
    "PipelineExecutor",
    "ReplayStage",
    "ReplayTimeline",
    "StageRecord",
    "TimelineRecorder",
    "WorkflowCoordinator",
    "WorkflowRequest",
    "WorkflowRun",
    "WorkflowTimeline",
    "project_intake",
    "reconstruct",
    "reference_request",
]
