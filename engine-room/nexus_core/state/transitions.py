"""Per-object lifecycle transition tables.

Each operational object's lifecycle (from its frozen contract, doc-24-aligned)
is encoded as an immutable :class:`StateMachine`. The ``MACHINES`` registry maps
each object's logical name to its machine so the lifecycle validator can enforce
legal transitions uniformly. These tables are the *rules*; the actual current
state is always a projection of the event log (ADR-001).
"""

from __future__ import annotations

from typing import Any

from nexus_core.contracts.enums import ArtifactStatus, ResourceAllocationState
from nexus_core.contracts.status import (
    CapabilityStatus,
    CheckpointStage,
    ContextPackageStatus,
    EventStage,
    ExecutionGraphStatus,
    ExecutionStrategyStatus,
    GoalStatus,
    IntentStatus,
    KnowledgeIngestionStatus,
    ObservationStage,
    PlanStatus,
    PolicyStatus,
    ReflectionStatus,
    SkillStatus,
    WorkPackageStatus,
)
from nexus_core.state.machine import StateMachine

# --------------------------------------------------------------------------- #
# Understanding pipeline                                                       #
# --------------------------------------------------------------------------- #

INTENT_MACHINE: StateMachine[IntentStatus] = StateMachine(
    name="Intent",
    transitions={
        IntentStatus.RECEIVED: frozenset({IntentStatus.INTERPRETING, IntentStatus.ABANDONED}),
        IntentStatus.INTERPRETING: frozenset(
            {IntentStatus.AWAITING_CLARIFICATION, IntentStatus.RESOLVED, IntentStatus.ABANDONED}
        ),
        IntentStatus.AWAITING_CLARIFICATION: frozenset(
            {IntentStatus.INTERPRETING, IntentStatus.ABANDONED}
        ),
        IntentStatus.RESOLVED: frozenset(),
        IntentStatus.ABANDONED: frozenset(),
    },
    initial=IntentStatus.RECEIVED,
    terminal=frozenset({IntentStatus.RESOLVED, IntentStatus.ABANDONED}),
    failure=frozenset({IntentStatus.ABANDONED}),
)

GOAL_MACHINE: StateMachine[GoalStatus] = StateMachine(
    name="Goal",
    transitions={
        GoalStatus.NORMALIZED: frozenset({GoalStatus.CONTEXTUALIZING, GoalStatus.ABANDONED}),
        GoalStatus.CONTEXTUALIZING: frozenset({GoalStatus.PLANNING, GoalStatus.ABANDONED}),
        GoalStatus.PLANNING: frozenset({GoalStatus.EXECUTING, GoalStatus.ABANDONED}),
        GoalStatus.EXECUTING: frozenset({GoalStatus.ACHIEVED, GoalStatus.ABANDONED}),
        GoalStatus.ACHIEVED: frozenset(),
        GoalStatus.ABANDONED: frozenset(),
    },
    initial=GoalStatus.NORMALIZED,
    terminal=frozenset({GoalStatus.ACHIEVED, GoalStatus.ABANDONED}),
    failure=frozenset({GoalStatus.ABANDONED}),
)

CONTEXT_PACKAGE_MACHINE: StateMachine[ContextPackageStatus] = StateMachine(
    name="ContextPackage",
    transitions={
        ContextPackageStatus.ASSEMBLING: frozenset(
            {ContextPackageStatus.VALIDATING, ContextPackageStatus.INVALIDATED}
        ),
        ContextPackageStatus.VALIDATING: frozenset(
            {ContextPackageStatus.READY, ContextPackageStatus.INVALIDATED}
        ),
        ContextPackageStatus.READY: frozenset(
            {ContextPackageStatus.ENRICHING, ContextPackageStatus.SUPERSEDED}
        ),
        ContextPackageStatus.ENRICHING: frozenset(
            {ContextPackageStatus.VALIDATING, ContextPackageStatus.SUPERSEDED}
        ),
        ContextPackageStatus.SUPERSEDED: frozenset(),
        ContextPackageStatus.INVALIDATED: frozenset(),
    },
    initial=ContextPackageStatus.ASSEMBLING,
    terminal=frozenset({ContextPackageStatus.SUPERSEDED, ContextPackageStatus.INVALIDATED}),
    failure=frozenset({ContextPackageStatus.INVALIDATED}),
)

PLAN_MACHINE: StateMachine[PlanStatus] = StateMachine(
    name="Plan",
    transitions={
        PlanStatus.DRAFT: frozenset({PlanStatus.READY, PlanStatus.CANCELLED}),
        PlanStatus.READY: frozenset(
            {PlanStatus.ACTIVE, PlanStatus.SUPERSEDED, PlanStatus.CANCELLED}
        ),
        PlanStatus.ACTIVE: frozenset(
            {PlanStatus.COMPLETED, PlanStatus.FAILED, PlanStatus.SUPERSEDED, PlanStatus.CANCELLED}
        ),
        PlanStatus.SUPERSEDED: frozenset(),
        PlanStatus.COMPLETED: frozenset(),
        PlanStatus.CANCELLED: frozenset(),
        PlanStatus.FAILED: frozenset(),
    },
    initial=PlanStatus.DRAFT,
    terminal=frozenset({PlanStatus.SUPERSEDED, PlanStatus.COMPLETED, PlanStatus.CANCELLED}),
    failure=frozenset({PlanStatus.FAILED}),
)

WORK_PACKAGE_MACHINE: StateMachine[WorkPackageStatus] = StateMachine(
    name="WorkPackage",
    transitions={
        WorkPackageStatus.CREATED: frozenset(
            {WorkPackageStatus.READY, WorkPackageStatus.CANCELLED}
        ),
        WorkPackageStatus.READY: frozenset(
            {
                WorkPackageStatus.EXECUTING,
                WorkPackageStatus.BLOCKED,
                WorkPackageStatus.CANCELLED,
                WorkPackageStatus.EXPIRED,
            }
        ),
        WorkPackageStatus.EXECUTING: frozenset(
            {
                WorkPackageStatus.PAUSED,
                WorkPackageStatus.COMPLETED,
                WorkPackageStatus.BLOCKED,
                WorkPackageStatus.FAILED,
                WorkPackageStatus.CANCELLED,
                WorkPackageStatus.EXPIRED,
            }
        ),
        WorkPackageStatus.PAUSED: frozenset(
            {WorkPackageStatus.EXECUTING, WorkPackageStatus.CANCELLED, WorkPackageStatus.EXPIRED}
        ),
        WorkPackageStatus.BLOCKED: frozenset(
            {WorkPackageStatus.READY, WorkPackageStatus.CANCELLED, WorkPackageStatus.EXPIRED}
        ),
        WorkPackageStatus.COMPLETED: frozenset(),
        WorkPackageStatus.FAILED: frozenset(),
        WorkPackageStatus.CANCELLED: frozenset(),
        WorkPackageStatus.EXPIRED: frozenset(),
    },
    initial=WorkPackageStatus.CREATED,
    terminal=frozenset(
        {WorkPackageStatus.COMPLETED, WorkPackageStatus.CANCELLED, WorkPackageStatus.EXPIRED}
    ),
    failure=frozenset({WorkPackageStatus.FAILED}),
)

EXECUTION_STRATEGY_MACHINE: StateMachine[ExecutionStrategyStatus] = StateMachine(
    name="ExecutionStrategy",
    transitions={
        ExecutionStrategyStatus.DRAFT: frozenset({ExecutionStrategyStatus.ACTIVE}),
        ExecutionStrategyStatus.ACTIVE: frozenset(
            {ExecutionStrategyStatus.SUPERSEDED, ExecutionStrategyStatus.RETIRED}
        ),
        ExecutionStrategyStatus.SUPERSEDED: frozenset({ExecutionStrategyStatus.RETIRED}),
        ExecutionStrategyStatus.RETIRED: frozenset(),
    },
    initial=ExecutionStrategyStatus.DRAFT,
    terminal=frozenset({ExecutionStrategyStatus.RETIRED}),
)

EXECUTION_GRAPH_MACHINE: StateMachine[ExecutionGraphStatus] = StateMachine(
    name="ExecutionGraph",
    transitions={
        ExecutionGraphStatus.CREATED: frozenset(
            {ExecutionGraphStatus.READY, ExecutionGraphStatus.CANCELLED}
        ),
        ExecutionGraphStatus.READY: frozenset(
            {ExecutionGraphStatus.EXECUTING, ExecutionGraphStatus.CANCELLED}
        ),
        ExecutionGraphStatus.EXECUTING: frozenset(
            {
                ExecutionGraphStatus.PAUSED,
                ExecutionGraphStatus.WAITING,
                ExecutionGraphStatus.BLOCKED,
                ExecutionGraphStatus.RECOVERING,
                ExecutionGraphStatus.COMPLETED,
                ExecutionGraphStatus.FAILED,
                ExecutionGraphStatus.CANCELLED,
            }
        ),
        ExecutionGraphStatus.PAUSED: frozenset(
            {ExecutionGraphStatus.EXECUTING, ExecutionGraphStatus.CANCELLED}
        ),
        ExecutionGraphStatus.WAITING: frozenset(
            {ExecutionGraphStatus.EXECUTING, ExecutionGraphStatus.CANCELLED}
        ),
        ExecutionGraphStatus.BLOCKED: frozenset(
            {ExecutionGraphStatus.EXECUTING, ExecutionGraphStatus.CANCELLED}
        ),
        ExecutionGraphStatus.RECOVERING: frozenset(
            {
                ExecutionGraphStatus.EXECUTING,
                ExecutionGraphStatus.FAILED,
                ExecutionGraphStatus.CANCELLED,
            }
        ),
        ExecutionGraphStatus.COMPLETED: frozenset(),
        ExecutionGraphStatus.FAILED: frozenset({ExecutionGraphStatus.RECOVERING}),
        ExecutionGraphStatus.CANCELLED: frozenset(),
    },
    initial=ExecutionGraphStatus.CREATED,
    terminal=frozenset({ExecutionGraphStatus.COMPLETED, ExecutionGraphStatus.CANCELLED}),
    failure=frozenset({ExecutionGraphStatus.FAILED}),
)

# --------------------------------------------------------------------------- #
# Capability / skill / resource                                                #
# --------------------------------------------------------------------------- #

SKILL_MACHINE: StateMachine[SkillStatus] = StateMachine(
    name="Skill",
    transitions={
        SkillStatus.REGISTERED: frozenset({SkillStatus.SELECTED}),
        SkillStatus.SELECTED: frozenset({SkillStatus.PREPARED, SkillStatus.CANCELLED}),
        SkillStatus.PREPARED: frozenset(
            {SkillStatus.EXECUTING, SkillStatus.BLOCKED, SkillStatus.CANCELLED}
        ),
        SkillStatus.EXECUTING: frozenset(
            {
                SkillStatus.VALIDATED,
                SkillStatus.BLOCKED,
                SkillStatus.FAILED,
                SkillStatus.CANCELLED,
                SkillStatus.EXPIRED,
            }
        ),
        SkillStatus.VALIDATED: frozenset({SkillStatus.COMPLETED, SkillStatus.FAILED}),
        SkillStatus.BLOCKED: frozenset(
            {SkillStatus.PREPARED, SkillStatus.CANCELLED, SkillStatus.EXPIRED}
        ),
        SkillStatus.COMPLETED: frozenset(),
        SkillStatus.FAILED: frozenset(),
        SkillStatus.CANCELLED: frozenset(),
        SkillStatus.EXPIRED: frozenset(),
    },
    initial=SkillStatus.REGISTERED,
    terminal=frozenset({SkillStatus.COMPLETED, SkillStatus.CANCELLED, SkillStatus.EXPIRED}),
    failure=frozenset({SkillStatus.FAILED}),
)

CAPABILITY_MACHINE: StateMachine[CapabilityStatus] = StateMachine(
    name="Capability",
    transitions={
        CapabilityStatus.DRAFT: frozenset({CapabilityStatus.REGISTERED}),
        CapabilityStatus.REGISTERED: frozenset({CapabilityStatus.ACTIVE}),
        CapabilityStatus.ACTIVE: frozenset({CapabilityStatus.DEPRECATED}),
        CapabilityStatus.DEPRECATED: frozenset({CapabilityStatus.RETIRED}),
        CapabilityStatus.RETIRED: frozenset(),
    },
    initial=CapabilityStatus.DRAFT,
    terminal=frozenset({CapabilityStatus.RETIRED}),
)

RESOURCE_MACHINE: StateMachine[ResourceAllocationState] = StateMachine(
    name="Resource",
    transitions={
        ResourceAllocationState.AVAILABLE: frozenset(
            {ResourceAllocationState.RESERVED, ResourceAllocationState.ALLOCATED}
        ),
        ResourceAllocationState.RESERVED: frozenset(
            {ResourceAllocationState.ALLOCATED, ResourceAllocationState.RELEASED}
        ),
        ResourceAllocationState.ALLOCATED: frozenset({ResourceAllocationState.RELEASED}),
        ResourceAllocationState.RELEASED: frozenset({ResourceAllocationState.AVAILABLE}),
    },
    initial=ResourceAllocationState.AVAILABLE,
    terminal=frozenset(),
)

# --------------------------------------------------------------------------- #
# Outputs / substrate                                                          #
# --------------------------------------------------------------------------- #

ARTIFACT_MACHINE: StateMachine[ArtifactStatus] = StateMachine(
    name="Artifact",
    transitions={
        ArtifactStatus.DRAFT: frozenset({ArtifactStatus.GENERATED}),
        ArtifactStatus.GENERATED: frozenset({ArtifactStatus.VALIDATED}),
        ArtifactStatus.VALIDATED: frozenset({ArtifactStatus.PUBLISHED}),
        ArtifactStatus.PUBLISHED: frozenset({ArtifactStatus.ARCHIVED}),
        ArtifactStatus.ARCHIVED: frozenset(),
    },
    initial=ArtifactStatus.DRAFT,
    terminal=frozenset({ArtifactStatus.ARCHIVED}),
)

OBSERVATION_MACHINE: StateMachine[ObservationStage] = StateMachine(
    name="Observation",
    transitions={
        ObservationStage.DERIVED: frozenset({ObservationStage.RECORDED}),
        ObservationStage.RECORDED: frozenset({ObservationStage.SUPERSEDED}),
        ObservationStage.SUPERSEDED: frozenset(),
    },
    initial=ObservationStage.DERIVED,
    terminal=frozenset({ObservationStage.SUPERSEDED}),
)

EVENT_MACHINE: StateMachine[EventStage] = StateMachine(
    name="Event",
    transitions={
        EventStage.OCCURRED: frozenset({EventStage.CREATED}),
        EventStage.CREATED: frozenset({EventStage.PUBLISHED}),
        EventStage.PUBLISHED: frozenset({EventStage.DELIVERED}),
        EventStage.DELIVERED: frozenset({EventStage.PROCESSED}),
        EventStage.PROCESSED: frozenset({EventStage.PERSISTED}),
        EventStage.PERSISTED: frozenset({EventStage.ARCHIVED}),
        EventStage.ARCHIVED: frozenset(),
    },
    initial=EventStage.OCCURRED,
    terminal=frozenset({EventStage.ARCHIVED}),
)

CHECKPOINT_MACHINE: StateMachine[CheckpointStage] = StateMachine(
    name="Checkpoint",
    transitions={
        CheckpointStage.CREATED: frozenset({CheckpointStage.PERSISTED}),
        CheckpointStage.PERSISTED: frozenset({CheckpointStage.AVAILABLE}),
        CheckpointStage.AVAILABLE: frozenset(
            {CheckpointStage.RESTORED, CheckpointStage.SUPERSEDED, CheckpointStage.ARCHIVED}
        ),
        CheckpointStage.RESTORED: frozenset({CheckpointStage.SUPERSEDED, CheckpointStage.ARCHIVED}),
        CheckpointStage.SUPERSEDED: frozenset({CheckpointStage.ARCHIVED}),
        CheckpointStage.ARCHIVED: frozenset(),
    },
    initial=CheckpointStage.CREATED,
    terminal=frozenset({CheckpointStage.ARCHIVED}),
)

POLICY_MACHINE: StateMachine[PolicyStatus] = StateMachine(
    name="Policy",
    transitions={
        PolicyStatus.REGISTERED: frozenset({PolicyStatus.VALIDATED}),
        PolicyStatus.VALIDATED: frozenset({PolicyStatus.ENABLED}),
        PolicyStatus.ENABLED: frozenset({PolicyStatus.DISABLED}),
        PolicyStatus.DISABLED: frozenset(),
    },
    initial=PolicyStatus.REGISTERED,
    terminal=frozenset({PolicyStatus.DISABLED}),
)

KNOWLEDGE_MACHINE: StateMachine[KnowledgeIngestionStatus] = StateMachine(
    name="Knowledge",
    transitions={
        KnowledgeIngestionStatus.CANDIDATE: frozenset({KnowledgeIngestionStatus.VALIDATING}),
        KnowledgeIngestionStatus.VALIDATING: frozenset(
            {KnowledgeIngestionStatus.ACCEPTED, KnowledgeIngestionStatus.REJECTED}
        ),
        KnowledgeIngestionStatus.ACCEPTED: frozenset(),
        KnowledgeIngestionStatus.REJECTED: frozenset(),
    },
    initial=KnowledgeIngestionStatus.CANDIDATE,
    terminal=frozenset({KnowledgeIngestionStatus.ACCEPTED, KnowledgeIngestionStatus.REJECTED}),
    failure=frozenset({KnowledgeIngestionStatus.REJECTED}),
)

REFLECTION_MACHINE: StateMachine[ReflectionStatus] = StateMachine(
    name="Reflection",
    transitions={
        ReflectionStatus.PENDING: frozenset({ReflectionStatus.ANALYZING}),
        ReflectionStatus.ANALYZING: frozenset(
            {ReflectionStatus.CANDIDATES_PROPOSED, ReflectionStatus.DISCARDED}
        ),
        ReflectionStatus.CANDIDATES_PROPOSED: frozenset(),
        ReflectionStatus.DISCARDED: frozenset(),
    },
    initial=ReflectionStatus.PENDING,
    terminal=frozenset({ReflectionStatus.CANDIDATES_PROPOSED, ReflectionStatus.DISCARDED}),
    failure=frozenset({ReflectionStatus.DISCARDED}),
)


# --------------------------------------------------------------------------- #
# Registry                                                                     #
# --------------------------------------------------------------------------- #

MACHINES: dict[str, StateMachine[Any]] = {
    "intent": INTENT_MACHINE,
    "goal": GOAL_MACHINE,
    "context_package": CONTEXT_PACKAGE_MACHINE,
    "plan": PLAN_MACHINE,
    "work_package": WORK_PACKAGE_MACHINE,
    "execution_strategy": EXECUTION_STRATEGY_MACHINE,
    "execution_graph": EXECUTION_GRAPH_MACHINE,
    "skill": SKILL_MACHINE,
    "capability": CAPABILITY_MACHINE,
    "resource": RESOURCE_MACHINE,
    "artifact": ARTIFACT_MACHINE,
    "observation": OBSERVATION_MACHINE,
    "event": EVENT_MACHINE,
    "checkpoint": CHECKPOINT_MACHINE,
    "policy": POLICY_MACHINE,
    "knowledge": KNOWLEDGE_MACHINE,
    "reflection": REFLECTION_MACHINE,
}


def machine_for(object_name: str) -> StateMachine[Any]:
    """Return the lifecycle :class:`StateMachine` for a logical object name.

    Raises ``KeyError`` with the known names if ``object_name`` is unregistered.
    """
    try:
        return MACHINES[object_name]
    except KeyError as exc:
        known = ", ".join(sorted(MACHINES))
        raise KeyError(f"no lifecycle machine for {object_name!r}; known: {known}") from exc
