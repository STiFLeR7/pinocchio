"""Cross-runtime execution + governance comparison (Milestones 4 & 6).

Proves the program's thesis end-to-end: the *same* governed workflow (the same Goal, Work
Packages, Plan, Orchestration, Harness, Runtime Manager, and Execution Engine) runs on Claude,
Gemini, or Shell by **adapter substitution alone**. Nothing upstream of the adapter changes;
only the runtime-specific artifacts (the produced files, the streamed output, the chosen
runtime's identity in ``runtime.*`` payloads) differ.

:class:`CrossRuntimeRunner` drives the existing :class:`~nexus_workflows.WorkflowCoordinator`
with an adapter factory that resolves a chosen runtime from an :class:`AdapterRegistry`
(Milestone 4). :func:`governance_signature` extracts the part of a run that must be **identical**
across runtimes — the work packages, the execution/validation/recovery decisions, and the
runtime-independent event-type skeleton — so a test can assert cross-runtime governance
equivalence directly (Milestone 6). Selection itself is the deterministic funnel in
:mod:`~nexus_runtime_adapters.selection` (Milestone 5).
"""

from __future__ import annotations

from dataclasses import dataclass

from nexus_core.contracts.base import Reference, Struct
from nexus_execution.adapter import RuntimeAdapter
from nexus_knowledge.persistence import KnowledgeRepositories
from nexus_runtime import SelectionResult
from nexus_runtime.events import (
    RUNTIME_ARTIFACT_EMITTED,
    RUNTIME_OUTPUT,
    RUNTIME_PROGRESS,
)
from nexus_runtime_adapters.catalog import build_default_adapter_registry
from nexus_runtime_adapters.registry import AdapterRegistry, RuntimeInvocationProfile
from nexus_runtime_adapters.selection import select_runtime
from nexus_workflows import PipelineBuilder, WorkflowCoordinator, WorkflowRequest, WorkflowRun
from nexus_workflows.pipeline import Pipeline

# The three ``runtime.*`` event types whose *count* legitimately varies by runtime: streamed
# output, progress milestones, and produced artifacts. Removing them leaves the governance
# skeleton — the RM preparation, allocation, start/finalize/teardown lifecycle, and every
# other engine's events — which is identical across runtimes (Milestone 6).
_RUNTIME_VARIABLE_EVENT_TYPES = frozenset(
    {RUNTIME_OUTPUT, RUNTIME_PROGRESS, RUNTIME_ARTIFACT_EMITTED}
)


@dataclass(frozen=True, slots=True)
class GovernanceSignature:
    """The runtime-independent fingerprint of a run — must match across every runtime."""

    work_package_ids: tuple[str, ...]
    execution_outcomes: tuple[str, ...]
    validation_decisions: tuple[str, ...]
    recovery_decisions: tuple[str, ...]
    governance_event_types: tuple[str, ...]
    reflection_candidate_count: int


def governance_signature(run: WorkflowRun) -> GovernanceSignature:
    """Extract the part of ``run`` that governance guarantees regardless of the runtime."""
    return GovernanceSignature(
        work_package_ids=run.work_package_ids,
        execution_outcomes=run.execution_outcomes,
        validation_decisions=run.validation_decisions,
        recovery_decisions=run.recovery_decisions,
        governance_event_types=tuple(
            e.type for e in run.events if e.type not in _RUNTIME_VARIABLE_EVENT_TYPES
        ),
        reflection_candidate_count=len(run.reflection_candidates),
    )


@dataclass(frozen=True, slots=True)
class CrossRuntimeRun:
    """One runtime's workflow outcome, tagged with the runtime it executed on."""

    runtime_identity: str
    run: WorkflowRun

    @property
    def governance(self) -> GovernanceSignature:
        """The runtime-independent governance fingerprint of this run."""
        return governance_signature(self.run)


class CrossRuntimeRunner:
    """Runs the same workflow across substituted runtimes and exposes the comparison."""

    def __init__(self, adapters: AdapterRegistry | None = None) -> None:
        self._adapters = adapters or build_default_adapter_registry()

    @property
    def adapters(self) -> AdapterRegistry:
        """The adapter registry backing this runner."""
        return self._adapters

    # -- selection (Milestone 5) --------------------------------------------- #

    def select(
        self,
        required_capability_refs: tuple[Reference, ...],
        runtime_policy: Struct,
        *,
        candidate_ids: tuple[str, ...] | None = None,
    ) -> SelectionResult:
        """Deterministically choose one runtime (capabilities + policy only, never AI)."""
        return select_runtime(
            self._adapters,
            required_capability_refs,
            runtime_policy,
            candidate_ids=candidate_ids,
        )

    # -- execution (Milestone 4/6) ------------------------------------------- #

    def run_on(
        self,
        runtime_identity: str,
        request: WorkflowRequest,
        *,
        knowledge_repositories: KnowledgeRepositories | None = None,
        pipeline: Pipeline | None = None,
    ) -> WorkflowRun:
        """Run ``request`` end-to-end on ``runtime_identity`` — adapter substitution only."""
        built = pipeline or PipelineBuilder(knowledge_repositories=knowledge_repositories).build()

        def factory(req: WorkflowRequest) -> RuntimeAdapter:
            return self._adapters.create(
                runtime_identity, profile=RuntimeInvocationProfile(fail=req.fail)
            )

        coordinator = WorkflowCoordinator(built, adapter_factory=factory)
        return coordinator.run(request)

    def run_matrix(
        self,
        request: WorkflowRequest,
        *,
        runtime_identities: tuple[str, ...] | None = None,
    ) -> tuple[CrossRuntimeRun, ...]:
        """Run ``request`` on each runtime and return the tagged outcomes (Milestone 4)."""
        identities = runtime_identities or self._adapters.identities()
        return tuple(
            CrossRuntimeRun(runtime_identity=identity, run=self.run_on(identity, request))
            for identity in identities
        )
