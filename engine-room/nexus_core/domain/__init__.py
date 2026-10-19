"""Immutable domain models — the canonical operational objects.

One module per object. Each model is a frozen Pydantic ``DomainObject`` that
implements its frozen logical contract in ``contracts/`` exactly. Domain models
are pure business objects: no persistence, no API, no transport, no runtime
logic. Sequence fields use ``tuple`` for immutability; by-id pointers use
``Reference``; a ``LIFECYCLE_NAME`` class var ties each model to its lifecycle
machine in ``nexus_core.state``.
"""

from nexus_core.domain.artifact import Artifact
from nexus_core.domain.capability import Capability
from nexus_core.domain.checkpoint import Checkpoint
from nexus_core.domain.context_package import ContextCategories, ContextPackage
from nexus_core.domain.event import Event
from nexus_core.domain.execution_graph import ExecutionGraph, GraphEdge, GraphNode
from nexus_core.domain.execution_strategy import ExecutionStrategy
from nexus_core.domain.goal import Goal, Scope
from nexus_core.domain.intent import Intent
from nexus_core.domain.knowledge import Knowledge
from nexus_core.domain.observation import Observation
from nexus_core.domain.plan import Milestone, Plan
from nexus_core.domain.policy import Policy
from nexus_core.domain.reflection import Reflection
from nexus_core.domain.resource import Resource
from nexus_core.domain.skill import Skill
from nexus_core.domain.work_package import WorkPackage

__all__ = [
    "Artifact",
    "Capability",
    "Checkpoint",
    "ContextCategories",
    "ContextPackage",
    "Event",
    "ExecutionGraph",
    "ExecutionStrategy",
    "Goal",
    "GraphEdge",
    "GraphNode",
    "Intent",
    "Knowledge",
    "Milestone",
    "Observation",
    "Plan",
    "Policy",
    "Reflection",
    "Resource",
    "Scope",
    "Skill",
    "WorkPackage",
]
