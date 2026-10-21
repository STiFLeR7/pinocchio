"""Grounded Context Engineering composition — DI wiring over an infrastructure context.

Mirrors :func:`~nexus_context.composition.build_context_engineering`: it reuses the P1
substrate unchanged — the Context Package repository is the same ``InMemoryRepository`` generic
(durable transparently over ``build_durable_infrastructure``, ADR-007), the event emitter is the
infrastructure context itself, and observability is the context's sink. It adds only the
:class:`~nexus_context.grounding.assembler.GroundingAssembler` over that substrate; the incumbent
Context Engineering layer is not modified.
"""

from __future__ import annotations

from dataclasses import dataclass

from nexus_context.events import TimestampSource
from nexus_context.grounding.assembler import GroundingAssembler, GroundingObservability
from nexus_context.grounding.selection import GroundingSelector
from nexus_context.service import ContextRepositories
from nexus_core.domain.context_package import ContextPackage
from nexus_infra import InfrastructureContext, InMemoryRepository


@dataclass(frozen=True, slots=True)
class GroundedContextEngineeringContext:
    """The wired grounded-context layer (immutable wiring, stateful assembler + repository)."""

    infrastructure: InfrastructureContext
    repositories: ContextRepositories
    assembler: GroundingAssembler


def build_grounded_context_engineering(
    infrastructure: InfrastructureContext,
    *,
    selector: GroundingSelector | None = None,
    timestamps: TimestampSource | None = None,
) -> GroundedContextEngineeringContext:
    """Wire a grounded Context Engineering context; the repository rides the P1 substrate."""
    obs = infrastructure.observability
    repositories = ContextRepositories(
        context_packages=InMemoryRepository[ContextPackage](
            "context_package", lambda c: c.identity, obs
        ),
    )
    assembler = GroundingAssembler(
        repositories,
        infrastructure,
        selector=selector,
        timestamps=timestamps,
        observability=GroundingObservability(obs),
    )
    return GroundedContextEngineeringContext(
        infrastructure=infrastructure,
        repositories=repositories,
        assembler=assembler,
    )
