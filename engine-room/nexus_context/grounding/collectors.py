"""Grounding collectors — turn selected grounding facts into the incumbent's raw fragments.

Each collector implements the incumbent :class:`~nexus_context.collectors.ContextCollector`
Protocol (``collect(goal, request) -> tuple[RawContextFragment, ...]``) and is constructed
with the grounding inputs + the selection verdict (the ``StaticContextCollector`` precedent:
a collector may carry its data). They surface **only what the selector selected**, by
reference, into the correct Context Category — so the incumbent pipeline (normalize → rank →
freshness → package) assembles them into the one Context Package unchanged.

The collectors describe facts; they never decide approach (the EngineeringStrategy facets are
surfaced as *context*, not re-derived — Contextualize receives the approach, INV: it never
decides it). Knowledge is surfaced by reference only (INV-06). One collector per grounding
stage: Intent, Repository, Historical, Knowledge, Strategy (constraint/resource/execution).
"""

from __future__ import annotations

from nexus_context.categories import ContextCategory, ContextSource
from nexus_context.collectors import ContextCollector
from nexus_context.grounding.model import GroundingInputs, GroundingSelection
from nexus_context.requests import ContextRequest, RawContextFragment
from nexus_core.domain.goal import Goal


def _selected_by_kind(selection: GroundingSelection) -> dict[str, list[str]]:
    """The selected artifact identifiers grouped by kind (deterministic order)."""
    grouped: dict[str, list[str]] = {}
    for record in selection.selected:
        grouped.setdefault(record.artifact_type, []).append(record.identifier)
    return grouped


class IntentGroundingCollector:
    """Intent Collection — surfaces the resolved intent + operator preferences as context."""

    def __init__(self, inputs: GroundingInputs) -> None:
        self._inputs = inputs

    def collect(self, goal: Goal, request: ContextRequest) -> tuple[RawContextFragment, ...]:
        analysis = self._inputs.intent
        if analysis is None:
            return ()
        out: list[RawContextFragment] = []
        intent = analysis.intent
        out.append(
            RawContextFragment(
                source=ContextSource.OPERATOR,
                category=ContextCategory.OPERATIONAL,
                key="resolved_intent",
                payload={
                    "detected_intent": intent.detected_intent,
                    "modality": intent.modality.value,
                    "resolved": analysis.resolved,
                },
                references=(f"intent:{analysis.identity}",),
            )
        )
        if analysis.operator_preferences:
            out.append(
                RawContextFragment(
                    source=ContextSource.OPERATOR,
                    category=ContextCategory.CONSTRAINT,
                    key="operator_preferences",
                    payload={"preferences": dict(sorted(analysis.operator_preferences.items()))},
                )
            )
        return tuple(out)


class RepositoryGroundingCollector:
    """Repository Grounding — repository facts + the selected repository artifacts, by reference."""

    def __init__(self, inputs: GroundingInputs, selection: GroundingSelection) -> None:
        self._inputs = inputs
        self._selected = _selected_by_kind(selection)

    def collect(self, goal: Goal, request: ContextRequest) -> tuple[RawContextFragment, ...]:
        profile = self._inputs.repository_profile
        if profile is None or not profile.exists:
            return ()
        observed = profile.timestamp or None
        out: list[RawContextFragment] = [
            RawContextFragment(
                source=ContextSource.WORKSPACE,
                category=ContextCategory.WORKSPACE,
                key="repository",
                payload={
                    "root": profile.root,
                    "repository_type": profile.repository_type,
                    "primary_language": profile.technology.primary_language,
                    "top_level_dirs": list(profile.structure.top_level_dirs),
                    "source_dirs": list(profile.structure.source_dirs),
                    "file_count": profile.file_count,
                },
                observed_at=observed,
                references=(f"repository:{profile.identity}",),
            ),
            RawContextFragment(
                source=ContextSource.RUNTIME,
                category=ContextCategory.RESOURCE,
                key="toolchain",
                payload={
                    "package_managers": list(profile.technology.package_managers),
                    "frameworks": list(profile.technology.frameworks),
                    "build_commands": list(profile.build.build_commands),
                    "test_command": profile.test.test_command,
                },
                observed_at=observed,
            ),
            RawContextFragment(
                source=ContextSource.WORKSPACE,
                category=ContextCategory.EXECUTION,
                key="validation_signals",
                payload={
                    "test_frameworks": list(profile.test.frameworks),
                    "ci_system": profile.ci.system,
                    "has_tests": profile.health.has_tests,
                    "has_ci": profile.health.has_ci,
                },
                observed_at=observed,
            ),
        ]
        out.extend(self._selected_fragments(observed))
        return tuple(out)

    def _selected_fragments(self, observed: str | None) -> list[RawContextFragment]:
        """One fragment per selected repository artifact kind, each carrying its references."""
        plan = (
            ("adr", ContextCategory.WORKSPACE, "selected_adrs", "adr"),
            ("contract", ContextCategory.EXECUTION, "selected_contracts", "contract"),
            ("invariant", ContextCategory.EXECUTION, "selected_invariants", "invariant"),
            ("architecture_doc", ContextCategory.WORKSPACE, "selected_architecture_docs", "arch"),
            ("module", ContextCategory.WORKSPACE, "selected_modules", "module"),
            ("package", ContextCategory.WORKSPACE, "selected_packages", "package"),
            ("file", ContextCategory.WORKSPACE, "selected_files", "file"),
        )
        out: list[RawContextFragment] = []
        for kind, category, key, ref_prefix in plan:
            ids = self._selected.get(kind, [])
            if not ids:
                continue
            out.append(
                RawContextFragment(
                    source=ContextSource.WORKSPACE,
                    category=category,
                    key=key,
                    payload={kind: ids},
                    observed_at=observed,
                    references=tuple(f"{ref_prefix}:{identifier}" for identifier in ids),
                )
            )
        return out


class HistoryGroundingCollector:
    """Historical Grounding — execution-history facts + the selected prior executions."""

    def __init__(self, inputs: GroundingInputs, selection: GroundingSelection) -> None:
        self._inputs = inputs
        self._selected = _selected_by_kind(selection)

    def collect(self, goal: Goal, request: ContextRequest) -> tuple[RawContextFragment, ...]:
        history = self._inputs.history_profile
        if history is None or not history.available:
            return ()
        observed = history.timestamp or None
        out: list[RawContextFragment] = [
            RawContextFragment(
                source=ContextSource.ENVIRONMENT,
                category=ContextCategory.HISTORICAL,
                key="execution_summary",
                payload=dict(sorted(history.as_facts().items())),
                observed_at=observed,
                references=(f"execution_history:{history.identity}",),
            )
        ]
        priors = self._selected.get("prior_execution", [])
        if priors:
            out.append(
                RawContextFragment(
                    source=ContextSource.ENVIRONMENT,
                    category=ContextCategory.HISTORICAL,
                    key="selected_prior_executions",
                    payload={"correlations": priors},
                    observed_at=observed,
                    references=tuple(f"execution:{cor}" for cor in priors),
                )
            )
        return tuple(out)


class KnowledgeGroundingCollector:
    """Knowledge Grounding — the selected knowledge items, by reference only (INV-06, read-only)."""

    def __init__(self, inputs: GroundingInputs, selection: GroundingSelection) -> None:
        self._inputs = inputs
        self._selected = frozenset(_selected_by_kind(selection).get("knowledge", ()))

    def collect(self, goal: Goal, request: ContextRequest) -> tuple[RawContextFragment, ...]:
        chosen = [item for item in self._inputs.knowledge if item.identity in self._selected]
        if not chosen:
            return ()
        items = [
            {
                "id": item.identity,
                "type": item.type.value,
                "domain": item.domain.value if item.domain is not None else None,
                "summary": item.understanding[:120].replace("\n", " "),
            }
            for item in sorted(chosen, key=lambda k: k.identity)
        ]
        return (
            RawContextFragment(
                source=ContextSource.KNOWLEDGE,
                category=ContextCategory.HISTORICAL,
                key="knowledge",
                payload={"items": items},
                references=tuple(f"knowledge:{item['id']}" for item in items),
            ),
        )


class StrategyGroundingCollector:
    """Strategy Grounding — the EngineeringStrategy facets surfaced as context (received, not decided)."""

    def __init__(self, inputs: GroundingInputs) -> None:
        self._inputs = inputs

    def collect(self, goal: Goal, request: ContextRequest) -> tuple[RawContextFragment, ...]:
        strategy = self._inputs.engineering_strategy
        if strategy is None:
            return ()
        rigor = strategy.validation_rigor.selection
        return (
            RawContextFragment(
                source=ContextSource.OPERATOR,
                category=ContextCategory.EXECUTION,
                key="context_objectives",
                payload={"objectives": list(strategy.context_objectives.selection)},
                references=(f"engineering_strategy:{strategy.identity}",),
            ),
            RawContextFragment(
                source=ContextSource.OPERATOR,
                category=ContextCategory.EXECUTION,
                key="validation_rigor",
                payload={
                    "rigor": rigor[0] if rigor else "standard",
                    "mandatory_evidence": list(rigor[1:]),
                },
            ),
            RawContextFragment(
                source=ContextSource.RUNTIME,
                category=ContextCategory.RESOURCE,
                key="runtime_capabilities",
                payload={"capabilities": list(strategy.runtime_preferences.selection)},
            ),
            RawContextFragment(
                source=ContextSource.OPERATOR,
                category=ContextCategory.CONSTRAINT,
                key="autonomy",
                payload={
                    "autonomy_level": strategy.autonomy_level.selection[0]
                    if strategy.autonomy_level.selection
                    else "gated",
                    "approval": list(strategy.autonomy_level.selection),
                },
            ),
        )


def grounding_collectors(
    inputs: GroundingInputs, selection: GroundingSelection
) -> tuple[ContextCollector, ...]:
    """The grounding collector set for one assembly (only sources that are present emit fragments)."""
    return (
        IntentGroundingCollector(inputs),
        RepositoryGroundingCollector(inputs, selection),
        HistoryGroundingCollector(inputs, selection),
        KnowledgeGroundingCollector(inputs, selection),
        StrategyGroundingCollector(inputs),
    )
