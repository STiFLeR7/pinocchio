"""Step 5 — Context Resolver (produce an immutable execution view; never modify Context).

Projects the already-resolved Context Package into a frozen *execution view* — the
read-only slice of operational understanding a runtime needs to act, carried by value
so the runtime cannot reach back and mutate the source Context Package (which Context
Engineering owns; the Harness never edits it). The view is a projection, not a copy
of authority: it references the Goal and embeds the eight Context Categories,
constraints, validation status, and known unknowns.
"""

from __future__ import annotations

from pydantic import Field

from nexus_core.contracts.base import Constraint, Reference, Struct, ValueObject
from nexus_core.domain.context_package import ContextCategories, ContextPackage
from nexus_harness.vocabulary import CONTEXT_TARGET_TYPE


class ContextView(ValueObject):
    """An immutable, runtime-facing projection of a Context Package."""

    reference: Reference
    identity: str
    goal_ref: Reference
    confidence: str
    context_categories: ContextCategories
    constraints: tuple[Constraint, ...] = ()
    resources: tuple[Reference, ...] = ()
    validation_status: Struct = Field(default_factory=dict)
    known_unknowns: tuple[str, ...] = ()


class ContextResolver:
    """Builds the immutable execution view from a resolved Context Package."""

    def resolve(self, context_package: ContextPackage) -> ContextView:
        """Project the Context Package into a frozen execution view (no mutation)."""
        return ContextView(
            reference=Reference(
                target_type=CONTEXT_TARGET_TYPE, identifier=context_package.identity
            ),
            identity=context_package.identity,
            goal_ref=context_package.goal_ref,
            confidence=context_package.confidence.value,
            context_categories=context_package.context_categories,
            constraints=context_package.constraints,
            resources=context_package.resources,
            validation_status=context_package.validation_status,
            known_unknowns=context_package.known_unknowns,
        )
