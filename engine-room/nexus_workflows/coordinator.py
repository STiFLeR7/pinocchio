"""WorkflowCoordinator -- drive every engine, in order, for one request (Milestone 1/2).

The coordinator composes the ten existing engines into one deterministic flow::

    Goal -> Context -> [Knowledge read] -> Plan -> Work Packages -> Execution Graph
         -> Orchestration -> Harness -> [project] -> Runtime -> Execution
         -> Validation -> Recovery -> Reflection -> [Knowledge write]

It contains **no business logic**: each step calls an existing engine's real entry point; the
coordinator only performs the sanctioned Harness->Runtime projection and the Reflection->Knowledge
candidate adaptation at their boundaries, and records a cross-layer :class:`WorkflowTimeline`.

The learning loop (Milestone 5) is realised exactly as INV-26 requires: before Planning the
coordinator **reads Knowledge** via a read-only query and folds the returned understanding into the
``PlanningRequest`` (as assumptions); Planning consumes a Knowledge query result, never Reflection.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from nexus_context import ContextRequest, context_reference
from nexus_core.contracts.base import Reference
from nexus_core.contracts.enums import ConfidenceLadder
from nexus_core.domain.context_package import ContextPackage
from nexus_core.domain.event import Event
from nexus_execution.adapter import RuntimeAdapter
from nexus_execution.results import ExecutionResult
from nexus_harness import CompilationRequest, ExecutionManifest, ExecutionPackage
from nexus_knowledge import KnowledgeCandidate, KnowledgeQuery
from nexus_orchestration import OrchestrationRequest, OrchestrationResult
from nexus_planning import PlanningRequest, PlanningResult
from nexus_recovery.plan import RecoveryPlan
from nexus_reflection.report import ReflectionReport
from nexus_runtime import PreparationRequest, RuntimeIntake
from nexus_runtime.runtime_session import RuntimeSession
from nexus_runtime_claude import ClaudeRuntimeAdapter, StubClaudeInvoker
from nexus_validation.report import ValidationReport
from nexus_workflows.pipeline import Pipeline
from nexus_workflows.projection import project_intake
from nexus_workflows.request import WorkflowRequest
from nexus_workflows.timeline import TimelineRecorder, WorkflowTimeline

AdapterFactory = Callable[["WorkflowRequest"], RuntimeAdapter]
"""Builds the runtime adapter for a request (the one cross-runtime substitution seam)."""


def _default_adapter_factory(request: WorkflowRequest) -> RuntimeAdapter:
    """The default: the Claude runtime, honoring the request's failure-path selection."""
    return ClaudeRuntimeAdapter(invoker=StubClaudeInvoker(fail=request.fail))


@dataclass(frozen=True, slots=True)
class WorkflowRun:
    """The immutable outcome of one end-to-end workflow execution."""

    goal_ref: Reference
    context_ref: Reference
    plan_ref: Reference
    work_package_ids: tuple[str, ...]
    session_ids: tuple[str, ...]
    execution_outcomes: tuple[str, ...]
    validation_decisions: tuple[str, ...]
    recovery_decisions: tuple[str, ...]
    reflection_ref: Reference
    reflection_candidates: tuple[str, ...]
    knowledge_item_ids: tuple[str, ...]
    knowledge_consumed: int
    served_knowledge_ids: tuple[str, ...]
    timeline: WorkflowTimeline
    events: tuple[Event, ...]

    @property
    def succeeded(self) -> bool:
        """Whether every execution completed normally (not a validation verdict)."""
        return bool(self.execution_outcomes) and all(
            outcome == "completed" for outcome in self.execution_outcomes
        )


class WorkflowCoordinator:
    """Runs the complete Goal->Knowledge pipeline over one wired :class:`Pipeline`."""

    def __init__(
        self,
        pipeline: Pipeline,
        *,
        adapter_factory: AdapterFactory | None = None,
    ) -> None:
        self._p = pipeline
        # The runtime adapter is the ONLY provider-specific choice in the pipeline; injecting
        # its factory (default: Claude) is what makes the workflow provider-agnostic. Every
        # other engine is driven identically regardless of the chosen runtime (Capability
        # Program 2 — the Runtime abstraction is genuinely provider-independent).
        self._adapter_factory = adapter_factory or _default_adapter_factory
        self._rec = TimelineRecorder(
            pipeline.infrastructure.event_store.read_all, pipeline.timestamps.now
        )

    def run(self, request: WorkflowRequest) -> WorkflowRun:
        """Drive every engine in order and return the run's outcome + timeline."""
        self._register_inputs(request)
        adapter = self._adapter_factory(request)
        # Register the runtime so Orchestration can offer it as a candidate (INV-37, candidates only).
        self._p.harness_registry.register(adapter.descriptor())

        package, context_ref = self._context(request)
        consumed = self._read_knowledge(request)
        planning = self._plan(request, context_ref, consumed)
        orch = self._orchestrate(context_ref, planning)
        packages, manifests = self._compile(package, planning, orch)
        sessions = self._prepare(adapter, packages, orch, manifests)

        results, reports, plans = self._execute(adapter, sessions)
        reflection = self._reflect(request, results, reports, plans)
        items = self._write_knowledge(request, reflection, reports, plans)
        served = self._p.knowledge.engine.serve(
            KnowledgeQuery(kind=request.knowledge_kind, subject=request.knowledge_subject)
        )

        return WorkflowRun(
            goal_ref=Reference(target_type="goal", identifier=request.goal.identity),
            context_ref=context_ref,
            plan_ref=Reference(target_type="plan", identifier=planning.plan.identity),
            work_package_ids=tuple(w.identifier for w in planning.work_packages),
            session_ids=tuple(s.identity for s, _ in sessions),
            execution_outcomes=tuple(r.outcome.value for r in results),
            validation_decisions=tuple(rp.decision.value for rp in reports),
            recovery_decisions=tuple(pl.decision.value for pl in plans),
            reflection_ref=reflection.reference(),
            reflection_candidates=tuple(c.summary for c in reflection.knowledge_candidates),
            knowledge_item_ids=items,
            knowledge_consumed=len(consumed),
            served_knowledge_ids=tuple(i.identity for i in served),
            timeline=self._rec.build(),
            events=tuple(self._p.infrastructure.event_store.read_all()),
        )

    # -- input registration (existing registries; no engine change) ---------- #

    def _register_inputs(self, request: WorkflowRequest) -> None:
        for capability in request.capabilities:
            self._p.capability_registry.register(capability)
            self._p.harness.sources.capabilities.register(capability)
        for skill in request.skills:
            self._p.harness.sources.skills.register(skill)

    # -- pipeline stages ----------------------------------------------------- #

    def _context(self, request: WorkflowRequest) -> tuple[ContextPackage, Reference]:
        self._rec.enter("context_engineering")
        result = self._p.context.service.engineer(
            request.goal,
            ContextRequest(
                fragments=request.context_fragments,
                correlation_identifier=request.correlation_identifier or None,
            ),
        )
        ref = context_reference(result.package)
        self._rec.complete((ref,))
        return result.package, ref

    def _read_knowledge(self, request: WorkflowRequest) -> tuple[str, ...]:
        self._rec.enter("knowledge", "knowledge_read")
        served = self._p.knowledge.engine.serve(
            KnowledgeQuery(kind=request.knowledge_kind, subject=request.knowledge_subject)
        )
        self._rec.complete()
        return tuple(item.understanding for item in served)

    def _plan(
        self, request: WorkflowRequest, context_ref: Reference, consumed: tuple[str, ...]
    ) -> PlanningResult:
        assumptions = tuple(f"prior-knowledge: {statement}" for statement in consumed)
        self._rec.enter("planning")
        planning = self._p.planning.service.plan(
            request.goal,
            PlanningRequest(
                work_items=request.work_items,
                context_ref=context_ref,
                assumptions=assumptions,
                correlation_identifier=request.correlation_identifier or None,
            ),
        )
        self._rec.complete(
            (
                Reference(target_type="plan", identifier=planning.plan.identity),
                Reference(
                    target_type="execution_graph", identifier=planning.execution_graph.identity
                ),
            )
        )
        return planning

    def _orchestrate(self, context_ref: Reference, planning: PlanningResult) -> OrchestrationResult:
        self._rec.enter("orchestration")
        result = self._p.orchestration.service.orchestrate(
            OrchestrationRequest(
                execution_graph=planning.execution_graph,
                execution_strategy=planning.execution_strategy,
                context_ref=context_ref,
            )
        )
        self._rec.complete(
            tuple(
                Reference(target_type="harness_request", identifier=h.identity)
                for h in result.harness_requests
            )
        )
        return result

    def _compile(
        self, package: ContextPackage, planning: PlanningResult, orch: OrchestrationResult
    ) -> tuple[tuple[ExecutionPackage, ...], tuple[ExecutionManifest, ...]]:
        sources = self._p.harness.sources
        sources.context_packages.add(package)
        sources.strategies.add(planning.execution_strategy)
        for work_package in planning.work_packages:
            sources.work_packages.add(work_package)
        self._rec.enter("harness")
        result = self._p.harness.service.compile(
            CompilationRequest(
                harness_requests=orch.harness_requests,
                session_ref=orch.session.execution_graph_ref,
            )
        )
        self._rec.complete(tuple(_package_ref(p) for p in result.packages))
        return result.packages, result.manifests

    def _prepare(
        self,
        adapter: RuntimeAdapter,
        packages: tuple[ExecutionPackage, ...],
        orch: OrchestrationResult,
        manifests: tuple[ExecutionManifest, ...],
    ) -> list[tuple[RuntimeSession, RuntimeIntake]]:
        runtime_by_node = {r.node: r for r in orch.runtime_requests}
        manifest_by_node = {m.node: m for m in manifests}
        intakes = tuple(
            project_intake(p, runtime_by_node.get(p.node), manifest_by_node.get(p.node))
            for p in packages
        )
        descriptor = adapter.descriptor()
        descriptor = descriptor.model_copy(
            update={"metadata": {**(descriptor.metadata or {}), "capacity": len(intakes)}}
        )
        self._p.runtime.manager.register_runtime(descriptor)
        self._rec.enter("runtime")
        prepared = self._p.runtime.manager.prepare(
            PreparationRequest(intakes=intakes, session_ref=None, correlation_identifier=None)
        )
        self._rec.complete()
        return list(zip(prepared.sessions, intakes, strict=True))

    def _execute(
        self,
        adapter: RuntimeAdapter,
        sessions: list[tuple[RuntimeSession, RuntimeIntake]],
    ) -> tuple[list[ExecutionResult], list[ValidationReport], list[RecoveryPlan]]:
        results: list[ExecutionResult] = []
        for session, intake in sessions:
            self._rec.enter("execution", f"execution:{intake.node}")
            result = self._p.execution.engine.execute(session, adapter, intake.work_package)
            self._rec.complete(result.artifact_refs)
            results.append(result)

        events = tuple(self._p.infrastructure.event_store.read_all())
        reports: list[ValidationReport] = []
        plans: list[RecoveryPlan] = []
        for (_session, intake), result in zip(sessions, results, strict=True):
            self._rec.enter("validation", f"validation:{intake.node}")
            report = self._p.validation.engine.validate(result, intake.work_package, events=events)
            self._rec.complete(report.evidence_refs)
            reports.append(report)
            self._rec.enter("recovery", f"recovery:{intake.node}")
            plan = self._p.recovery.engine.recover(report, result, events=events)
            self._rec.complete()
            plans.append(plan)
        return results, reports, plans

    def _reflect(
        self,
        request: WorkflowRequest,
        results: list[ExecutionResult],
        reports: list[ValidationReport],
        plans: list[RecoveryPlan],
    ) -> ReflectionReport:
        self._rec.enter("reflection")
        report = self._p.reflection.engine.reflect(
            request.scope,
            execution_results=tuple(results),
            validation_reports=tuple(reports),
            recovery_plans=tuple(plans),
            events=tuple(self._p.infrastructure.event_store.read_all()),
        )
        self._rec.complete((report.reference(),))
        return report

    def _write_knowledge(
        self,
        request: WorkflowRequest,
        reflection: ReflectionReport,
        reports: list[ValidationReport],
        plans: list[RecoveryPlan],
    ) -> tuple[str, ...]:
        self._rec.enter("knowledge", "knowledge_write")
        items: list[str] = []
        for advisory in reflection.knowledge_candidates:
            pattern = next(
                (
                    pattern
                    for pattern in reflection.patterns
                    if advisory.source_pattern_ref is not None
                    and pattern.identity == advisory.source_pattern_ref.identifier
                ),
                None,
            )
            pattern_refs = {ref.identifier for ref in pattern.evidence_refs} if pattern else set()
            report_sessions = {
                plan.session_ref.identifier for plan in plans if plan.identity in pattern_refs
            }
            matching_reports = tuple(
                report
                for report in reports
                if (
                    report.identity in pattern_refs
                    or report.session_ref.identifier in pattern_refs
                    or report.session_ref.identifier in report_sessions
                    or (not pattern_refs and len(reports) == 1)
                )
            )
            if not matching_reports:
                continue
            evidence = tuple(
                {
                    (ref.target_type, ref.identifier): ref
                    for report in matching_reports
                    for ref in report.evidence_refs
                }.values()
            )
            if not evidence:
                continue
            candidate = KnowledgeCandidate(
                identity=advisory.identity,
                kind=request.knowledge_kind,
                subject=request.knowledge_subject,
                statement=advisory.summary,
                confidence=ConfidenceLadder.OBSERVED,
                evidence_refs=evidence,
                source_goal_ref=Reference(target_type="goal", identifier=request.goal.identity),
                source_run_refs=tuple(report.session_ref for report in matching_reports),
                validation_report_refs=tuple(report.reference() for report in matching_reports),
                domain=request.goal.domain,
                applicability={"domain": request.goal.domain.value},
                originating_reflection_ref=reflection.reference(),
                source_pattern_ref=advisory.source_pattern_ref,
                correlation_identifier=reflection.correlation_identifier,
            )
            outcome = self._p.knowledge.engine.ingest(candidate)
            if outcome.item is not None:
                items.append(outcome.item.identity)
        self._rec.complete()
        return tuple(items)


def _package_ref(package: ExecutionPackage) -> Reference:
    return Reference(target_type="execution_package", identifier=package.identity)
