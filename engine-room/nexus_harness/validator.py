"""Step 1 — Harness Validator (resolve and confirm the primary references).

Validates a Harness Request's shape, then resolves and confirms its three *primary*
references — the Work Package it performs, the Context Package it acts within, and
(when present) the Execution Strategy that governs it — against the injected
resolution sources. A dangling primary reference is a fail-closed error
(:class:`UnresolvedReferenceError`); nothing is invented or defaulted. The resolved
objects are returned in a :class:`ValidatedRequest` so the rest of the pipeline does
not look them up twice.

It validates references only. It never executes the Work Package, evaluates a
policy, or mutates anything it reads.
"""

from __future__ import annotations

from nexus_core.contracts.base import ValueObject
from nexus_core.domain.context_package import ContextPackage
from nexus_core.domain.execution_strategy import ExecutionStrategy
from nexus_core.domain.work_package import WorkPackage
from nexus_harness.sources import HarnessSources
from nexus_harness.validators import UnresolvedReferenceError, validate_request_shape
from nexus_orchestration.harness_requests import HarnessRequest


class ValidatedRequest(ValueObject):
    """A Harness Request whose three primary references have been resolved."""

    request: HarnessRequest
    work_package: WorkPackage
    context_package: ContextPackage
    strategy: ExecutionStrategy | None = None


class HarnessValidator:
    """Resolves and confirms the Work Package, Context Package, and Strategy."""

    def __init__(self, sources: HarnessSources) -> None:
        self._sources = sources

    def validate(self, request: HarnessRequest) -> ValidatedRequest:
        """Confirm shape and primary references; return the resolved objects."""
        validate_request_shape(request)
        work_package = self._sources.work_packages.get(request.work_package_ref.identifier)
        if work_package is None:
            raise UnresolvedReferenceError(
                f"work package {request.work_package_ref.identifier!r} for harness request "
                f"{request.identity!r} is not resolvable"
            )
        context_package = self._resolve_context(request)
        strategy = self._resolve_strategy(request)
        return ValidatedRequest(
            request=request,
            work_package=work_package,
            context_package=context_package,
            strategy=strategy,
        )

    def _resolve_context(self, request: HarnessRequest) -> ContextPackage:
        if request.context_ref is None:
            raise UnresolvedReferenceError(
                f"harness request {request.identity!r} carries no context reference"
            )
        context_package = self._sources.context_packages.get(request.context_ref.identifier)
        if context_package is None:
            raise UnresolvedReferenceError(
                f"context package {request.context_ref.identifier!r} for harness request "
                f"{request.identity!r} is not resolvable"
            )
        return context_package

    def _resolve_strategy(self, request: HarnessRequest) -> ExecutionStrategy | None:
        if request.execution_strategy_ref is None:
            return None
        strategy = self._sources.strategies.get(request.execution_strategy_ref.identifier)
        if strategy is None:
            raise UnresolvedReferenceError(
                f"execution strategy {request.execution_strategy_ref.identifier!r} for harness "
                f"request {request.identity!r} is not resolvable"
            )
        return strategy
