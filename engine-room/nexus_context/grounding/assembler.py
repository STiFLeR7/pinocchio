"""The grounded assembler — deterministic assembly that feeds the incumbent producer.

:class:`GroundingAssembler` runs P9's assembly pipeline (Intent → Repository → Historical →
Knowledge → Constraint/Resource → **Selection** → Packaging) and delegates the final
packaging + persistence to the incumbent :class:`~nexus_context.service.ContextEngineeringService`
— the single constitutional producer of the Context Package (INV-02, INV-07). It adds a
*producer of grounded inputs*, never a second producer of the object.

Two grounding facts anchor determinism and replay (INV-17), both in the ``context.*`` namespace:

- ``context.grounding.selected`` — embeds the full :class:`GroundingSelection` (selected *and*
  omitted, each with a reason), so the selection replays without re-selecting.
- ``context.grounding.assembled`` — embeds the produced Context Package, so replaying the
  ``context.grounding.*`` stream reconstructs the grounded ExecutionContext without rebuilding.

Assembly is a pure function of the recorded facts; the only captured-as-data value is the
injected event timestamp, never used in identity or selection.
"""

from __future__ import annotations

from nexus_context import ids
from nexus_context.collectors import (
    ContextCollector,
    GoalContextCollector,
    RequestFragmentCollector,
)
from nexus_context.events import (
    SystemTimestampSource,
    TimestampSource,
    build_event,
)
from nexus_context.grounding.collectors import grounding_collectors
from nexus_context.grounding.model import (
    GroundedContextResult,
    GroundingInputs,
    GroundingSelection,
)
from nexus_context.grounding.selection import GroundingSelector
from nexus_context.requests import ContextRequest
from nexus_context.service import ContextEngineeringService, ContextRepositories
from nexus_core.contracts.base import Reference, Struct
from nexus_core.domain.goal import Goal
from nexus_core.events.interfaces import EventEmitter
from nexus_infra import NullObservability, Observability, content_hash

CONTEXT_GROUNDING_SELECTED = "context.grounding.selected"
CONTEXT_GROUNDING_ASSEMBLED = "context.grounding.assembled"

# Artifact kinds surfaced as Context Package supporting_artifacts (document-like grounding).
_SUPPORTING_KINDS = frozenset(
    {
        "adr",
        "contract",
        "invariant",
        "architecture_doc",
        "file",
        "module",
        "package",
        "knowledge",
        "prior_execution",
    }
)


class GroundingObservability:
    """Grounding-scoped counters over the P1 sink (derived convenience, never authoritative)."""

    def __init__(self, observability: Observability | None = None) -> None:
        self._obs: Observability = observability or NullObservability()

    def selected(self, *, selected: int, omitted: int) -> None:
        self._obs.increment("context.grounding.selected")
        self._obs.observe("context.grounding.selected_count", float(selected))
        self._obs.observe("context.grounding.omitted_count", float(omitted))

    def assembled(self, *, item_count: int) -> None:
        self._obs.increment("context.grounding.assembled")
        self._obs.observe("context.grounding.item_count", float(item_count))


class GroundingAssembler:
    """Assembles grounded context deterministically and feeds the incumbent Context producer."""

    def __init__(
        self,
        repositories: ContextRepositories,
        emitter: EventEmitter,
        *,
        selector: GroundingSelector | None = None,
        timestamps: TimestampSource | None = None,
        observability: GroundingObservability | None = None,
    ) -> None:
        self._repos = repositories
        self._emitter = emitter
        self._selector = selector or GroundingSelector()
        self._timestamps = timestamps or SystemTimestampSource()
        self._obs = observability or GroundingObservability()

    def assemble(
        self, inputs: GroundingInputs, request: ContextRequest | None = None
    ) -> GroundedContextResult:
        """Select, record, and package the grounded ExecutionContext for ``inputs.goal``."""
        goal = inputs.goal
        base = request or ContextRequest()
        correlation = self._correlation(goal, base)

        selection = self._selector.select(inputs)
        self._obs.selected(selected=len(selection.selected), omitted=len(selection.omitted))
        self._emit(
            goal, correlation, CONTEXT_GROUNDING_SELECTED, "selected", selection.as_payload()
        )

        collectors: tuple[ContextCollector, ...] = (
            GoalContextCollector(),
            RequestFragmentCollector(),
            *grounding_collectors(inputs, selection),
        )
        enriched = self._enrich_request(selection, base, correlation)
        service = ContextEngineeringService(
            self._repos, collectors, self._emitter, timestamps=self._timestamps
        )
        result = service.engineer(goal, enriched)

        self._obs.assembled(item_count=len(result.items))
        self._emit(
            goal,
            correlation,
            CONTEXT_GROUNDING_ASSEMBLED,
            "assembled",
            {
                "context": result.package.identity,
                "goal": goal.identity,
                "selected": len(selection.selected),
                "omitted": len(selection.omitted),
                "package": dict(result.package.model_dump(mode="json")),
            },
        )
        return GroundedContextResult(result=result, selection=selection)

    # -- request enrichment -------------------------------------------------- #

    def _enrich_request(
        self, selection: GroundingSelection, base: ContextRequest, correlation: str
    ) -> ContextRequest:
        """Fold the selection into the request: supporting artifacts + explained source gaps."""
        supporting = list(base.supporting_artifacts)
        seen = {(ref.target_type, ref.identifier) for ref in supporting}
        for record in selection.selected:
            if record.artifact_type in _SUPPORTING_KINDS:
                key = (record.artifact_type, record.identifier)
                if key not in seen:
                    seen.add(key)
                    supporting.append(
                        Reference(target_type=record.artifact_type, identifier=record.identifier)
                    )
        gaps = set(base.known_unknowns)
        for record in selection.omitted:
            if record.identifier == "(source absent)":
                gaps.add(f"grounding_gap:{record.source}:{record.reason}")
        return base.model_copy(
            update={
                "supporting_artifacts": tuple(supporting),
                "known_unknowns": tuple(sorted(gaps)),
                "correlation_identifier": base.correlation_identifier or correlation,
            }
        )

    # -- events -------------------------------------------------------------- #

    def _emit(
        self, goal: Goal, correlation: str, event_type: str, kind: str, payload: Struct
    ) -> None:
        context_identity = ids.context_id(goal.identity)
        identifier = f"evt-{context_identity}-grounding-{kind}-{content_hash(payload)[:16]}"
        self._emitter.emit(
            build_event(identifier, event_type, correlation, payload, self._timestamps.now())
        )

    @staticmethod
    def _correlation(goal: Goal, request: ContextRequest) -> str:
        if request.correlation_identifier is not None:
            return request.correlation_identifier
        if goal.correlation is not None:
            return goal.correlation.correlation_identifier
        return ids.correlation_id(goal.identity)
