"""BriefingCoordinator — generate a briefing product through the existing control plane (M1).

The coordinator is a **consumer**: it composes the existing end-to-end pipeline
(:class:`~nexus_workflows.WorkflowCoordinator`) and the existing runtime adapter ecosystem
(:class:`~nexus_runtime_adapters.AdapterRegistry`) to generate a briefing — Brief Request →
Context → Knowledge → Planning → Execution → Validation → Recovery → Reflection → Knowledge Update
→ Brief Composer → Rendered Brief. It contains **no planning, execution, validation, recovery,
reflection, or knowledge logic**; every stage is an existing engine's real entry point, and the
composition into a brief is delegated to :class:`~nexus_briefings.composer.BriefComposer`.

Runtime selection stays the existing Runtime Manager's job: the coordinator resolves the chosen
runtime's adapter from the registry and hands it to the workflow coordinator's substitution seam
(Capability Program 2). Selecting *which* runtime for a policy is the existing deterministic
:func:`~nexus_runtime_adapters.select_runtime` funnel.
"""

from __future__ import annotations

from nexus_briefings.brieftype import BRIEFING_CAPABILITY, BriefType, operational_digest
from nexus_briefings.composer import BriefComposer
from nexus_briefings.session import BriefingSession
from nexus_briefings.workflow import BriefingWorkflow
from nexus_core.contracts.base import Reference, Struct
from nexus_execution.adapter import RuntimeAdapter
from nexus_knowledge.persistence import KnowledgeRepositories
from nexus_runtime import SelectionResult
from nexus_runtime_adapters import (
    AdapterRegistry,
    RuntimeInvocationProfile,
    build_default_adapter_registry,
    select_runtime,
)
from nexus_workflows import PipelineBuilder, WorkflowCoordinator, WorkflowRequest, WorkflowRun
from nexus_workflows.coordinator import AdapterFactory
from nexus_workflows.pipeline import Pipeline

_DEFAULT_RUNTIME = "claude-code"


class BriefingCoordinator:
    """Generates a briefing product over the existing control plane and composes the brief."""

    def __init__(
        self,
        adapters: AdapterRegistry | None = None,
        *,
        composer: BriefComposer | None = None,
    ) -> None:
        self._adapters = adapters or build_default_adapter_registry()
        self._composer = composer or BriefComposer()

    @property
    def adapters(self) -> AdapterRegistry:
        """The adapter registry backing this coordinator."""
        return self._adapters

    # -- runtime selection (existing deterministic funnel) ------------------- #

    def select_runtime(
        self,
        runtime_policy: Struct,
        *,
        candidate_ids: tuple[str, ...] | None = None,
    ) -> SelectionResult:
        """Deterministically choose a runtime for a briefing (capabilities + policy only)."""
        required = (Reference(target_type="capability", identifier=BRIEFING_CAPABILITY),)
        return select_runtime(self._adapters, required, runtime_policy, candidate_ids=candidate_ids)

    # -- generation (drives the existing pipeline) --------------------------- #

    def generate(
        self,
        brief_type: BriefType | None = None,
        *,
        runtime_identity: str = _DEFAULT_RUNTIME,
        run: str = "b1",
        fail: bool = False,
        knowledge_repositories: KnowledgeRepositories | None = None,
        pipeline: Pipeline | None = None,
    ) -> BriefingSession:
        """Generate one briefing on ``runtime_identity`` and return the session."""
        resolved = brief_type or operational_digest()
        built = pipeline or PipelineBuilder(knowledge_repositories=knowledge_repositories).build()
        request = BriefingWorkflow(resolved).request(run=run, fail=fail)
        coordinator = WorkflowCoordinator(built, adapter_factory=self._factory(runtime_identity))
        wf_run: WorkflowRun = coordinator.run(request)
        return BriefingSession(
            brief_type=resolved,
            runtime_identity=runtime_identity,
            run=wf_run,
            brief=self._composer.compose(resolved, runtime_identity, wf_run),
            knowledge_repositories=built.knowledge.repositories,
        )

    def generate_across(
        self,
        brief_type: BriefType | None = None,
        *,
        runtime_identities: tuple[str, ...] | None = None,
        run: str = "b1",
        fail: bool = False,
    ) -> tuple[BriefingSession, ...]:
        """Generate the same briefing on each runtime (multi-runtime, adapter substitution)."""
        resolved = brief_type or operational_digest()
        identities = runtime_identities or self._adapters.identities()
        return tuple(
            self.generate(resolved, runtime_identity=identity, run=run, fail=fail)
            for identity in identities
        )

    # -- helpers ------------------------------------------------------------- #

    def _factory(self, runtime_identity: str) -> AdapterFactory:
        def factory(request: WorkflowRequest) -> RuntimeAdapter:
            return self._adapters.create(
                runtime_identity, profile=RuntimeInvocationProfile(fail=request.fail)
            )

        return factory
