"""ResearchCoordinator — autonomously drive a research topic through the existing platform.

The coordinator is a **consumer**: it composes the existing end-to-end pipeline
(:class:`~nexus_workflows.WorkflowCoordinator`) and the existing runtime adapter ecosystem
(:class:`~nexus_runtime_adapters.AdapterRegistry`) to run a complete research workflow — Context →
Knowledge → Planning → Orchestration → Harness → Runtime → Execution → Validation → Recovery →
Reflection → Knowledge → Brief. It contains **no planning, execution, validation, recovery,
reflection, or knowledge logic**; every stage is an existing engine's real entry point.

Runtime selection stays the existing Runtime Manager's job: the coordinator resolves the chosen
runtime's adapter from the registry and hands it to the workflow coordinator's substitution seam
(Capability Program 2). Selecting *which* runtime for a policy is the existing deterministic
:func:`~nexus_runtime_adapters.select_runtime` funnel.
"""

from __future__ import annotations

from nexus_core.contracts.base import Reference, Struct
from nexus_execution.adapter import RuntimeAdapter
from nexus_knowledge.persistence import KnowledgeRepositories
from nexus_research.brief import build_brief
from nexus_research.session import ResearchSession
from nexus_research.topic import RESEARCH_CAPABILITY, ResearchTopic, reference_topic
from nexus_research.workflow import ResearchWorkflow
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


class ResearchCoordinator:
    """Runs a complete autonomous research workflow over the existing control plane."""

    def __init__(self, adapters: AdapterRegistry | None = None) -> None:
        self._adapters = adapters or build_default_adapter_registry()

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
        """Deterministically choose a runtime for a research stage (capabilities + policy only)."""
        required = (Reference(target_type="capability", identifier=RESEARCH_CAPABILITY),)
        return select_runtime(self._adapters, required, runtime_policy, candidate_ids=candidate_ids)

    # -- execution (drives the existing pipeline) ---------------------------- #

    def research(
        self,
        topic: ResearchTopic | None = None,
        *,
        runtime_identity: str = _DEFAULT_RUNTIME,
        run: str = "r1",
        fail: bool = False,
        knowledge_repositories: KnowledgeRepositories | None = None,
        pipeline: Pipeline | None = None,
    ) -> ResearchSession:
        """Run one research workflow on ``runtime_identity`` and return the session."""
        resolved_topic = topic or reference_topic()
        built = pipeline or PipelineBuilder(knowledge_repositories=knowledge_repositories).build()
        request = ResearchWorkflow(resolved_topic).request(run=run, fail=fail)
        coordinator = WorkflowCoordinator(built, adapter_factory=self._factory(runtime_identity))
        wf_run: WorkflowRun = coordinator.run(request)
        return ResearchSession(
            topic=resolved_topic,
            runtime_identity=runtime_identity,
            run=wf_run,
            brief=build_brief(resolved_topic, runtime_identity, wf_run),
            knowledge_repositories=built.knowledge.repositories,
        )

    def research_across(
        self,
        topic: ResearchTopic | None = None,
        *,
        runtime_identities: tuple[str, ...] | None = None,
        run: str = "r1",
        fail: bool = False,
    ) -> tuple[ResearchSession, ...]:
        """Run the same research workflow on each runtime (Milestone 3, adapter substitution)."""
        resolved_topic = topic or reference_topic()
        identities = runtime_identities or self._adapters.identities()
        return tuple(
            self.research(resolved_topic, runtime_identity=identity, run=run, fail=fail)
            for identity in identities
        )

    # -- helpers ------------------------------------------------------------- #

    def _factory(self, runtime_identity: str) -> AdapterFactory:
        def factory(request: WorkflowRequest) -> RuntimeAdapter:
            return self._adapters.create(
                runtime_identity, profile=RuntimeInvocationProfile(fail=request.fail)
            )

        return factory
