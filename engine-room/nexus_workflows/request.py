"""WorkflowRequest -- the immutable description of one end-to-end operational workflow.

A request carries everything the :class:`~nexus_workflows.coordinator.WorkflowCoordinator` needs to
drive the full pipeline from a Goal: the Goal itself, the raw context fragments to engineer, the
deterministic decomposition into work items, the abstract Capabilities and Skills to register, and
the Knowledge subject the run's learning attaches to. ``fail`` selects the failing runtime path for
failure-scenario validation (Milestone 6).

This is pure integration input -- it introduces no new domain concept; every field is an existing
``nexus_core`` / engine value object.
"""

from __future__ import annotations

from dataclasses import dataclass

from nexus_context import RawContextFragment
from nexus_core.contracts.enums import KnowledgeType
from nexus_core.domain import Capability, Goal
from nexus_core.domain.skill import Skill
from nexus_planning import WorkItemSpec


@dataclass(frozen=True, slots=True)
class WorkflowRequest:
    """The immutable specification of one workflow execution (Goal -> Knowledge)."""

    goal: Goal
    work_items: tuple[WorkItemSpec, ...]
    knowledge_subject: str
    scope: str
    context_fragments: tuple[RawContextFragment, ...] = ()
    capabilities: tuple[Capability, ...] = ()
    skills: tuple[Skill, ...] = ()
    knowledge_kind: KnowledgeType = KnowledgeType.LESSON
    fail: bool = False
    runtime_identity: str = "claude-code"
    correlation_identifier: str = ""
