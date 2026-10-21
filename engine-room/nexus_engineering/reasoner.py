"""The constitutional reasoner — EI's genuine, deterministic engineering inference.

This is where EI **reasons**: it synthesizes a coherent Engineering Strategy from the Goal, the
Estimation Report, the Policy ceiling, Knowledge, Repository Understanding, Preferences, and
Environment Facts. It is *not* a routing table returning a fixed answer — every facet weighs
multiple signals, records the evidence that drove it, and carries a confidence.

**The determinism seam (INV-17).** :class:`Reasoner` is a protocol: the reasoning *strategy* is
pluggable, so an LLM-backed reasoner can be injected ("reason freely"). The constitutional default
:class:`DeterministicReasoner` reasons deterministically so the decision is auditable and replays
without re-inference — reason once, the engine emits once, replay forever. Whichever reasoner runs,
its output is recorded as an immutable decision; replay reads the record, never re-reasons.

The reasoner produces the Strategy value; the engine (``engine.py``) records it. No randomness, no
clock, no LLM here; no import of any downstream engine (Planning/Orchestration/Execution/…).
"""

from __future__ import annotations

from typing import Protocol

from nexus_core.contracts.enums import ApprovalTaxonomy, InterpretationConfidence, Priority
from nexus_engineering import ids
from nexus_engineering.model import EngineeringStrategy, ReasoningInputs, Recommendation
from nexus_engineering.vocabulary import (
    ApproachType,
    AutonomyLevel,
    ExecutionStyle,
    ObservabilityLevel,
    RecoveryPosture,
    RiskLevel,
    ValidationRigor,
    WorkClassification,
)

REASONER_VERSION = "1"

# --- signal tables (additive vocabularies, not a decision table) ------------ #

_CLASS_SIGNALS: dict[WorkClassification, tuple[str, ...]] = {
    WorkClassification.BUG_FIX: (
        "bug",
        "fix",
        "defect",
        "error",
        "crash",
        "regression",
        "broken",
        "failing",
        "issue",
    ),
    WorkClassification.FEATURE: (
        "add",
        "implement",
        "feature",
        "build",
        "create",
        "support",
        "introduce",
    ),
    WorkClassification.REFACTOR: (
        "refactor",
        "cleanup",
        "restructure",
        "simplify",
        "rename",
        "reorganize",
        "tidy",
    ),
    WorkClassification.INVESTIGATION: (
        "investigate",
        "diagnose",
        "analyze",
        "understand",
        "root",
        "explore",
        "why",
    ),
    WorkClassification.MIGRATION: ("migrate", "migration", "upgrade", "port", "convert"),
    WorkClassification.RESEARCH: (
        "research",
        "survey",
        "compare",
        "evaluate",
        "prototype",
        "spike",
        "study",
    ),
    WorkClassification.DOCUMENTATION: (
        "document",
        "documentation",
        "readme",
        "docs",
        "guide",
        "explain",
    ),
    WorkClassification.RELEASE: ("release", "deploy", "publish", "ship", "tag", "rollout"),
}
_DOMAIN_NUDGE = {
    "research": WorkClassification.RESEARCH,
    "writing": WorkClassification.DOCUMENTATION,
}

_IRREVERSIBLE_SIGNALS = (
    "production",
    "prod",
    "irreversible",
    "main branch",
    "deploy",
    "delete",
    "drop",
    "customer",
    "partner",
    "live",
    "payment",
    "billing",
)
_REVERSIBLE_SIGNALS = ("branch", "revert", "sandbox", "dry-run", "dry run", "local", "draft")

_BASE_RISK: dict[WorkClassification, RiskLevel] = {
    WorkClassification.RELEASE: RiskLevel.HIGH,
    WorkClassification.MIGRATION: RiskLevel.HIGH,
    WorkClassification.BUG_FIX: RiskLevel.MEDIUM,
    WorkClassification.FEATURE: RiskLevel.MEDIUM,
    WorkClassification.REFACTOR: RiskLevel.MEDIUM,
    WorkClassification.GENERIC: RiskLevel.MEDIUM,
    WorkClassification.INVESTIGATION: RiskLevel.LOW,
    WorkClassification.RESEARCH: RiskLevel.LOW,
    WorkClassification.DOCUMENTATION: RiskLevel.LOW,
}

_APPROACH: dict[WorkClassification, ApproachType] = {
    WorkClassification.FEATURE: ApproachType.INCREMENTAL,
    WorkClassification.REFACTOR: ApproachType.REFACTOR_SAFE,
    WorkClassification.INVESTIGATION: ApproachType.EXPLORATORY,
    WorkClassification.MIGRATION: ApproachType.SPIKE_THEN_IMPLEMENT,
    WorkClassification.RESEARCH: ApproachType.RESEARCH_FIRST,
    WorkClassification.DOCUMENTATION: ApproachType.INCREMENTAL,
    WorkClassification.RELEASE: ApproachType.VALIDATION_FIRST,
    WorkClassification.GENERIC: ApproachType.INVESTIGATE_FIRST,
}

_RUNTIME_CAPS: dict[str, tuple[str, ...]] = {
    "software": ("code-generation", "filesystem", "version-control", "high-context"),
    "research": ("web-search", "synthesis", "high-context"),
    "writing": ("writing", "filesystem"),
    "operations": ("shell", "filesystem", "observability"),
    "business": ("synthesis", "high-context"),
    "personal": ("high-context",),
}

_SKILLS: dict[WorkClassification, tuple[str, ...]] = {
    WorkClassification.BUG_FIX: (
        "root-cause-analysis",
        "implementation",
        "regression-testing",
        "reporting",
    ),
    WorkClassification.FEATURE: ("design", "implementation", "testing", "reporting"),
    WorkClassification.REFACTOR: ("static-analysis", "refactoring", "regression-testing"),
    WorkClassification.INVESTIGATION: ("analysis", "synthesis", "reporting"),
    WorkClassification.MIGRATION: (
        "analysis",
        "implementation",
        "migration-verification",
        "regression-testing",
    ),
    WorkClassification.RESEARCH: ("research", "synthesis", "reporting"),
    WorkClassification.DOCUMENTATION: ("analysis", "writing"),
    WorkClassification.RELEASE: ("release-verification", "regression-testing", "reporting"),
    WorkClassification.GENERIC: ("analysis", "implementation", "reporting"),
}

_CONTEXT_OBJECTIVES: dict[WorkClassification, tuple[str, ...]] = {
    WorkClassification.BUG_FIX: (
        "locate the defect from the report",
        "understand the failing module, its tests, and recent change history",
    ),
    WorkClassification.FEATURE: (
        "understand the target module and its integration points",
        "identify existing tests and conventions",
    ),
    WorkClassification.REFACTOR: (
        "map the code to be restructured and its callers",
        "identify the covering tests",
    ),
    WorkClassification.INVESTIGATION: (
        "identify the subsystem in question and its recent changes",
    ),
    WorkClassification.MIGRATION: (
        "inventory what must move and its dependents",
        "identify verification points",
    ),
    WorkClassification.RESEARCH: ("survey prior art for the research question",),
    WorkClassification.DOCUMENTATION: ("identify the subject and its authoritative source",),
    WorkClassification.RELEASE: ("confirm the release scope and its validation gates",),
    WorkClassification.GENERIC: ("establish the situation before acting",),
}

_MANDATORY_EVIDENCE: dict[WorkClassification, tuple[str, ...]] = {
    WorkClassification.BUG_FIX: (
        "reproduction fixed",
        "regression suite green",
        "no unrelated diff",
    ),
    WorkClassification.REFACTOR: ("regression suite green", "unchanged public contract"),
    WorkClassification.MIGRATION: ("migration verified", "regression suite green"),
    WorkClassification.RELEASE: ("release checks green", "regression suite green"),
    WorkClassification.FEATURE: ("new behavior tested", "regression suite green"),
}

_RISK_ORDER = (RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL)
_RIGOR_ORDER = (
    ValidationRigor.LOW,
    ValidationRigor.STANDARD,
    ValidationRigor.HIGH,
    ValidationRigor.STRICT,
)
_RIGOR_FOR_RISK = {
    RiskLevel.LOW: ValidationRigor.STANDARD,
    RiskLevel.MEDIUM: ValidationRigor.STANDARD,
    RiskLevel.HIGH: ValidationRigor.HIGH,
    RiskLevel.CRITICAL: ValidationRigor.STRICT,
}
_AUTONOMY_FOR_RISK = {
    RiskLevel.LOW: AutonomyLevel.AUTONOMOUS,
    RiskLevel.MEDIUM: AutonomyLevel.SUPERVISED,
    RiskLevel.HIGH: AutonomyLevel.GATED,
    RiskLevel.CRITICAL: AutonomyLevel.MANUAL,
}
_GOAL_CONFIDENCE = {
    InterpretationConfidence.HIGH: 0.9,
    InterpretationConfidence.MEDIUM: 0.6,
    InterpretationConfidence.LOW: 0.35,
    InterpretationConfidence.UNKNOWN: 0.2,
}
# Estimation's ComplexityBand values, ordered trivial → very_high (consumed, not redefined).
_COMPLEXITY_ORDER = ("trivial", "low", "moderate", "high", "very_high")


def _raise(level: RiskLevel, steps: int = 1) -> RiskLevel:
    return _RISK_ORDER[min(len(_RISK_ORDER) - 1, _RISK_ORDER.index(level) + steps)]


def _lower(level: RiskLevel, steps: int = 1) -> RiskLevel:
    return _RISK_ORDER[max(0, _RISK_ORDER.index(level) - steps)]


def _goal_text(inputs: ReasoningInputs) -> str:
    g = inputs.goal
    return " ".join(filter(None, (g.outcome, g.success_definition, g.rationale))).lower()


class Reasoner(Protocol):
    """The reasoning seam: any strategy that turns immutable inputs into an Engineering Strategy."""

    version: str

    def reason(self, inputs: ReasoningInputs, *, now: str) -> EngineeringStrategy: ...


class DeterministicReasoner:
    """The constitutional default: deterministic, evidence-weighing engineering inference."""

    version = REASONER_VERSION

    def reason(self, inputs: ReasoningInputs, *, now: str = "") -> EngineeringStrategy:
        goal = inputs.goal
        text = _goal_text(inputs)

        classification = self._classify(inputs, text)
        klass = WorkClassification(classification.selection[0])
        risk = self._risk(inputs, text, klass)
        approach = self._approach(inputs, klass, risk)
        complexity = self._complexity(inputs)
        rigor = self._validation(inputs, klass, risk)
        recovery = self._recovery(risk, text)
        autonomy = self._autonomy(inputs, risk)
        auto_level = AutonomyLevel(autonomy.selection[0])
        observability = self._observability(risk, auto_level)
        execution = self._execution_style(approach, complexity)

        overall_conf = self._overall_confidence(inputs, classification.confidence)
        coherence = self._coherence(risk, rigor, auto_level, inputs)

        strategy = EngineeringStrategy(
            identity="",  # filled below from content
            subject_identifier=goal.identity,
            correlation_identifier=_correlation(inputs),
            reasoner_version=self.version,
            engineering_objective=goal.success_definition or goal.outcome,
            classification=classification,
            approach=approach,
            complexity_class=complexity,
            execution_style=execution,
            context_objectives=self._context_objectives(klass),
            skill_requirements=self._skills(klass),
            runtime_preferences=self._runtime(inputs),
            validation_rigor=rigor,
            coordination_intent=self._coordination(execution, recovery, risk),
            recovery_posture=recovery,
            autonomy_level=autonomy,
            risk_assessment=self._risk_recommendation(inputs, text, klass, risk),
            observability=observability,
            rationale=self._rationale(klass, approach, risk, auto_level),
            confidence=overall_conf,
            coherence_notes=coherence,
            estimation_ref=inputs.estimation.identity if inputs.estimation is not None else None,
            policy_context=inputs.policy_context,
            knowledge_refs=tuple(sorted(k.identity for k in inputs.knowledge)),
            timestamp=now,
        )
        return strategy.model_copy(update={"identity": ids.strategy_id(inputs, self.version)})

    # -- facet reasoners ---------------------------------------------------- #

    def _classify(self, inputs: ReasoningInputs, text: str) -> Recommendation:
        scores: dict[WorkClassification, int] = {}
        evidence: list[str] = []
        for klass, tokens in _CLASS_SIGNALS.items():
            hits = [t for t in tokens if t in text]
            if hits:
                scores[klass] = len(hits)
                evidence.append(f"{klass.value}: matched {sorted(hits)}")
        chain = [f"goal domain = {inputs.goal.domain.value}"]
        nudged = _DOMAIN_NUDGE.get(inputs.goal.domain.value)
        if nudged is not None:
            scores[nudged] = scores.get(nudged, 0) + 1
            chain.append(f"domain nudge → +1 {nudged.value}")

        assumptions: tuple[str, ...] = ()
        if not scores:
            chosen, confidence = WorkClassification.GENERIC, 0.3
            assumptions = ("no classification signal in the goal; defaulted to generic",)
            chain.append("no signal → generic")
        else:
            top = max(scores.values())
            # deterministic tie-break: fixed enum declaration order.
            chosen = next(k for k in _CLASS_SIGNALS if scores.get(k, 0) == top)
            if nudged is not None and scores.get(nudged, 0) == top:
                chosen = nudged
            confidence = round(min(0.95, 0.5 + 0.15 * top), 4)
            chain.append(f"highest-scoring classification = {chosen.value} (score {top})")
        return Recommendation(
            facet="classification",
            selection=(chosen.value,),
            reasoning_chain=tuple(chain),
            contributing_evidence=tuple(evidence) or ("goal outcome text",),
            confidence=confidence,
            assumptions=assumptions,
        )

    def _risk(self, inputs: ReasoningInputs, text: str, klass: WorkClassification) -> RiskLevel:
        level = _BASE_RISK[klass]
        if any(s in text for s in _IRREVERSIBLE_SIGNALS):
            level = _raise(level)
        if inputs.goal.priority is Priority.CRITICAL:
            level = _raise(level)
        if inputs.estimation is not None:
            band = inputs.estimation.complexity.band.value
            if _COMPLEXITY_ORDER.index(band) >= _COMPLEXITY_ORDER.index("high"):
                level = _raise(level)
        if any(s in text for s in _REVERSIBLE_SIGNALS):
            level = _lower(level)
        return level

    def _risk_recommendation(
        self, inputs: ReasoningInputs, text: str, klass: WorkClassification, risk: RiskLevel
    ) -> Recommendation:
        evidence = [f"base risk for {klass.value} = {_BASE_RISK[klass].value}"]
        est_infl: list[str] = []
        irreversible = [s for s in _IRREVERSIBLE_SIGNALS if s in text]
        reversible = [s for s in _REVERSIBLE_SIGNALS if s in text]
        if irreversible:
            evidence.append(f"irreversibility signals {sorted(irreversible)} → raised")
        if reversible:
            evidence.append(f"reversibility signals {sorted(reversible)} → lowered")
        if inputs.goal.priority is Priority.CRITICAL:
            evidence.append("goal priority critical → raised")
        if inputs.estimation is not None:
            band = inputs.estimation.complexity.band.value
            est_infl.append(
                f"complexity band {band} (from estimation {inputs.estimation.identity})"
            )
            if inputs.estimation.cost.amount > 0:
                est_infl.append(
                    f"cost estimate {inputs.estimation.cost.amount} {inputs.estimation.cost.currency}"
                )
        reversibility = (
            "low" if irreversible and not reversible else "high" if reversible else "medium"
        )
        return Recommendation(
            facet="risk_assessment",
            selection=(risk.value,),
            reasoning_chain=(
                f"blast radius inferred from constraints/outcome; reversibility = {reversibility}",
                f"envelope = {risk.value}",
            ),
            contributing_evidence=tuple(evidence),
            confidence=0.7,
            estimation_influences=tuple(est_infl),
        )

    def _approach(
        self, inputs: ReasoningInputs, klass: WorkClassification, risk: RiskLevel
    ) -> Recommendation:
        if klass is WorkClassification.BUG_FIX:
            hard = risk in (RiskLevel.HIGH, RiskLevel.CRITICAL) or self._complex_at_least(
                inputs, "moderate"
            )
            approach = ApproachType.INVESTIGATE_FIRST if hard else ApproachType.SURGICAL
        else:
            approach = _APPROACH[klass]
        chain = [f"classification {klass.value} → approach {approach.value}"]
        know_infl = self._knowledge_for(inputs, ("strategy", "pattern"))
        if know_infl:
            chain.append("prior strategy/pattern knowledge considered")
        return Recommendation(
            facet="approach",
            selection=(approach.value,),
            reasoning_chain=tuple(chain),
            contributing_evidence=(f"risk {risk.value}",),
            confidence=0.75,
            knowledge_influences=know_infl,
        )

    def _complexity(self, inputs: ReasoningInputs) -> Recommendation:
        if inputs.estimation is None:
            return Recommendation(
                facet="complexity_class",
                selection=("moderate",),
                reasoning_chain=("no estimation report; conservative default",),
                contributing_evidence=("estimation absent",),
                confidence=0.3,
                assumptions=("Estimation Report unavailable; assumed moderate complexity",),
            )
        band = inputs.estimation.complexity.band.value
        return Recommendation(
            facet="complexity_class",
            selection=(band,),
            reasoning_chain=(
                f"consumed Estimation complexity band = {band} (EI never re-estimates)",
            ),
            contributing_evidence=(f"complexity score {inputs.estimation.complexity.score}",),
            confidence=round(inputs.estimation.confidence.value, 4),
            estimation_influences=(
                f"complexity estimate {inputs.estimation.complexity.identity}",
                f"estimation confidence {inputs.estimation.confidence.value}",
            ),
        )

    def _execution_style(
        self, approach: Recommendation, complexity: Recommendation
    ) -> Recommendation:
        band = complexity.selection[0]
        appr = approach.selection[0]
        if appr in (ApproachType.RESEARCH_FIRST.value, ApproachType.EXPLORATORY.value) and band in (
            "high",
            "very_high",
        ):
            style = ExecutionStyle.MIXED
        else:
            style = ExecutionStyle.SEQUENTIAL
        return Recommendation(
            facet="execution_style",
            selection=(style.value,),
            reasoning_chain=(f"approach {appr} + complexity {band} → {style.value}",),
            contributing_evidence=(f"approach {appr}", f"complexity {band}"),
            confidence=0.6,
        )

    def _validation(
        self, inputs: ReasoningInputs, klass: WorkClassification, risk: RiskLevel
    ) -> Recommendation:
        rigor = _RIGOR_FOR_RISK[risk]
        floor_note = ""
        if klass in (WorkClassification.RELEASE, WorkClassification.MIGRATION) and (
            _RIGOR_ORDER.index(rigor) < _RIGOR_ORDER.index(ValidationRigor.HIGH)
        ):
            rigor = ValidationRigor.HIGH
            floor_note = f"{klass.value} floors rigor at high"
        evidence = list(_MANDATORY_EVIDENCE.get(klass, ("independently verifiable evidence",)))
        chain = [f"risk {risk.value} → rigor {rigor.value} (rigor ≥ risk floor, INV-20)"]
        if floor_note:
            chain.append(floor_note)
        return Recommendation(
            facet="validation_rigor",
            selection=(rigor.value, *evidence),
            reasoning_chain=tuple(chain),
            contributing_evidence=("a runtime self-report of success is insufficient (INV-20)",),
            confidence=0.8,
            estimation_influences=("risk derived with estimation inputs",),
        )

    def _recovery(self, risk: RiskLevel, text: str) -> Recommendation:
        if risk in (RiskLevel.HIGH, RiskLevel.CRITICAL) or "irreversible" in text:
            posture = RecoveryPosture.CHECKPOINT_AND_ESCALATE
        else:
            posture = RecoveryPosture.RETRY_THEN_ESCALATE
        return Recommendation(
            facet="recovery_posture",
            selection=(posture.value,),
            reasoning_chain=(
                f"risk {risk.value} → {posture.value} (bounded retry; Recovery decides — INV-22)",
            ),
            contributing_evidence=(f"risk {risk.value}",),
            confidence=0.7,
        )

    def _autonomy(self, inputs: ReasoningInputs, risk: RiskLevel) -> Recommendation:
        base = _AUTONOMY_FOR_RISK[risk]
        pol = inputs.policy_context
        chain = [f"risk {risk.value} → base autonomy {base.value}"]
        pol_infl: list[str] = []
        gates: list[str] = []
        if risk in (RiskLevel.HIGH, RiskLevel.CRITICAL):
            gates.append("approval gate before any irreversible action")
        if pol is None:
            level = _min_autonomy(base, AutonomyLevel.GATED)
            chain.append(
                "no Policy Context → assume not-permitted, route to approval gate (fail-closed, INV-30)"
            )
            gates.append("approval gate: policy context unavailable")
            assumptions: tuple[str, ...] = (
                "Policy Context absent; autonomy capped at gated (fail-closed)",
            )
        else:
            assumptions = ()
            pol_infl.append(f"policy decision = {pol.decision} (matched {pol.matched_policy})")
            if not pol.allowed and not pol.requires_approval:
                level = AutonomyLevel.MANUAL
                chain.append(
                    "policy denies → manual (human decision required, EI proposes; Policy decides — INV-29)"
                )
                gates.append("manual gate: policy denies the action")
            elif pol.requires_approval:
                level = _min_autonomy(base, AutonomyLevel.GATED)
                chain.append(f"policy requires approval ({pol.approval_level}) → cap at gated")
                gates.append(
                    f"approval gate: policy requires {pol.approval_level or ApprovalTaxonomy.HUMAN_REVIEW.value}"
                )
            else:
                level = base
                chain.append("policy allows → base autonomy stands (still ≤ policy ceiling)")
        return Recommendation(
            facet="autonomy_level",
            selection=(level.value, *gates),
            reasoning_chain=tuple(chain),
            contributing_evidence=tuple(gates) or ("no additional gates",),
            confidence=0.75,
            assumptions=assumptions,
            policy_influences=tuple(pol_infl),
        )

    def _observability(self, risk: RiskLevel, autonomy: AutonomyLevel) -> Recommendation:
        if autonomy in (AutonomyLevel.MANUAL, AutonomyLevel.GATED) or risk in (
            RiskLevel.HIGH,
            RiskLevel.CRITICAL,
        ):
            level = ObservabilityLevel.AUDIT
        elif autonomy is AutonomyLevel.SUPERVISED:
            level = ObservabilityLevel.VERBOSE
        else:
            level = ObservabilityLevel.STANDARD
        return Recommendation(
            facet="observability",
            selection=(level.value,),
            reasoning_chain=(f"risk {risk.value} + autonomy {autonomy.value} → {level.value}",),
            contributing_evidence=(f"autonomy {autonomy.value}",),
            confidence=0.7,
        )

    def _context_objectives(self, klass: WorkClassification) -> Recommendation:
        objectives = _CONTEXT_OBJECTIVES[klass]
        return Recommendation(
            facet="context_objectives",
            selection=objectives,
            reasoning_chain=(
                f"classification {klass.value} → what must be understood first (→ Context Engineering)",
            ),
            contributing_evidence=(f"classification {klass.value}",),
            confidence=0.7,
        )

    def _skills(self, klass: WorkClassification) -> Recommendation:
        skills = _SKILLS[klass]
        return Recommendation(
            facet="skill_requirements",
            selection=skills,
            reasoning_chain=(
                f"classification {klass.value} → required capabilities, composed sequentially "
                "(capabilities, never concrete Skills — INV-33)",
            ),
            contributing_evidence=(f"classification {klass.value}",),
            confidence=0.7,
        )

    def _runtime(self, inputs: ReasoningInputs) -> Recommendation:
        preferred = _RUNTIME_CAPS.get(inputs.goal.domain.value, ("high-context",))
        assumptions: tuple[str, ...] = ()
        chain = [
            f"domain {inputs.goal.domain.value} → preferred capabilities {list(preferred)} (capabilities, not providers — INV-32)"
        ]
        if inputs.environment_capabilities:
            available = set(inputs.environment_capabilities)
            feasible = tuple(c for c in preferred if c in available)
            dropped = tuple(c for c in preferred if c not in available)
            if dropped:
                chain.append(
                    f"dropped unavailable capabilities {list(dropped)} (Runtime Preferences ⊆ available — INV-36)"
                )
            selection = feasible or ("high-context",)
        else:
            selection = preferred
            assumptions = ("Environment Facts absent; assumed preferred capabilities available",)
        return Recommendation(
            facet="runtime_preferences",
            selection=selection,
            reasoning_chain=tuple(chain),
            contributing_evidence=(f"domain {inputs.goal.domain.value}",),
            confidence=0.7,
            assumptions=assumptions,
        )

    def _coordination(
        self, execution: Recommendation, recovery: Recommendation, risk: RiskLevel
    ) -> Recommendation:
        checkpoint = (
            "; checkpoint before the irreversible step"
            if risk in (RiskLevel.HIGH, RiskLevel.CRITICAL)
            else ""
        )
        intent = f"{execution.selection[0]}; {recovery.selection[0]}{checkpoint}"
        return Recommendation(
            facet="coordination_intent",
            selection=(intent,),
            reasoning_chain=(
                "coordination + recovery posture as declarative intent (Execution Strategy formalizes — INV-05)",
            ),
            contributing_evidence=(
                f"execution {execution.selection[0]}",
                f"recovery {recovery.selection[0]}",
            ),
            confidence=0.65,
        )

    # -- confidence, coherence, rationale ----------------------------------- #

    def _overall_confidence(self, inputs: ReasoningInputs, classification_conf: float) -> float:
        parts = [_GOAL_CONFIDENCE[inputs.goal.confidence], classification_conf]
        if inputs.estimation is not None:
            parts.append(inputs.estimation.confidence.value)
        completeness = sum(
            0.1
            for present in (
                inputs.repository_understanding,
                inputs.operator_preferences,
                inputs.knowledge,
            )
            if present
        )
        return round(min(1.0, sum(parts) / len(parts) + completeness), 4)

    def _coherence(
        self,
        risk: RiskLevel,
        rigor: Recommendation,
        autonomy: AutonomyLevel,
        inputs: ReasoningInputs,
    ) -> tuple[str, ...]:
        notes = [
            f"autonomy {autonomy.value} ≤ policy ceiling ({'no policy' if inputs.policy_context is None else inputs.policy_context.decision})",
            f"validation rigor {rigor.selection[0]} ≥ risk floor for {risk.value}",
        ]
        return tuple(notes)

    def _rationale(
        self,
        klass: WorkClassification,
        approach: Recommendation,
        risk: RiskLevel,
        autonomy: AutonomyLevel,
    ) -> str:
        return (
            f"Classified as {klass.value}; chose a {approach.selection[0]} approach at {risk.value} risk; "
            f"autonomy {autonomy.value} within the policy ceiling. One coherent decision (INV-31)."
        )

    # -- helpers ------------------------------------------------------------ #

    def _complex_at_least(self, inputs: ReasoningInputs, band: str) -> bool:
        if inputs.estimation is None:
            return False
        return _COMPLEXITY_ORDER.index(
            inputs.estimation.complexity.band.value
        ) >= _COMPLEXITY_ORDER.index(band)

    def _knowledge_for(self, inputs: ReasoningInputs, types: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(
            sorted(
                k.identity
                for k in inputs.knowledge
                if k.type.value in types and (k.domain is None or k.domain == inputs.goal.domain)
            )
        )


def _min_autonomy(a: AutonomyLevel, ceiling: AutonomyLevel) -> AutonomyLevel:
    # Cap at the ceiling: return the MORE restrictive (lower-autonomy) of the two.
    order = (
        AutonomyLevel.MANUAL,
        AutonomyLevel.GATED,
        AutonomyLevel.SUPERVISED,
        AutonomyLevel.AUTONOMOUS,
    )
    return order[min(order.index(a), order.index(ceiling))]


def _correlation(inputs: ReasoningInputs) -> str:
    if inputs.goal.correlation is not None:
        return inputs.goal.correlation.correlation_identifier
    return inputs.goal.identity
