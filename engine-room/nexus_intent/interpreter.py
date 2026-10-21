"""The understanding interpreter — Intent Resolution's deterministic interpretation.

This is where Intent Resolution **understands**: it normalizes a raw operator request into an
objective, detects its domain, extracts constraints and operator preferences, detects ambiguity and
missing information, generates clarification requests, and assesses confidence. It determines *what*
the operator wants; it never decides *how* (no estimation, no execution reasoning, no runtime/skill
choice, no policy, no orchestration).

**The determinism seam (INV-17).** :class:`Interpreter` is a protocol — an LLM-backed interpreter
attaches behind it ("clarification preferred over incorrect execution" still applies). The
constitutional default :class:`DeterministicInterpreter` interprets deterministically so the
understanding is auditable and replays without re-understanding — understand once, emit once, replay
forever. No randomness, no clock here; no import of any downstream engine.
"""

from __future__ import annotations

import re
from typing import Protocol

from nexus_core.contracts.base import Constraint, Correlation, Reference
from nexus_core.contracts.enums import Domain, InterpretationConfidence, Priority
from nexus_core.domain.goal import Goal, Scope
from nexus_core.domain.intent import Intent
from nexus_intent import ids
from nexus_intent.model import (
    ClarificationKind,
    ClarificationRequest,
    IntentAnalysis,
    IntentConfidence,
    IntentRequest,
)

INTERPRETER_VERSION = "1"

_IMPERATIVE_PREFIXES = (
    "please ",
    "can you ",
    "could you ",
    "would you ",
    "i need you to ",
    "i want you to ",
    "i'd like you to ",
    "help me ",
    "i need ",
    "i want ",
    "we need ",
    "let's ",
)

_DOMAIN_SIGNALS: dict[Domain, tuple[str, ...]] = {
    Domain.SOFTWARE: (
        "code",
        "bug",
        "fix",
        "implement",
        "refactor",
        "deploy",
        "test",
        "api",
        "function",
        "module",
        "repository",
        "repo",
        "build",
        "compile",
        "merge",
        "cli",
        "config",
        "configuration",
        "export",
        "exports",
        "command",
        "commands",
        "json",
        "csv",
        "version",
        "option",
    ),
    Domain.RESEARCH: (
        "research",
        "survey",
        "compare",
        "evaluate",
        "investigate",
        "study",
        "analyze",
    ),
    Domain.WRITING: ("write", "document", "draft", "readme", "article", "blog", "documentation"),
    Domain.OPERATIONS: ("deploy", "monitor", "provision", "scale", "backup", "restart", "server"),
    Domain.BUSINESS: ("report", "invoice", "customer", "revenue", "budget", "proposal"),
    Domain.PERSONAL: ("remind", "schedule", "personal", "note"),
}

_CONSTRAINT_MARKERS: dict[str, tuple[str, ...]] = {
    "prohibition": ("must not", "do not", "don't", "never", "without touching", "avoid"),
    "restriction": ("only ", "just ", "solely"),
    "limit": ("within ", "under ", "by end of", "before ", "budget", "no more than", "at most"),
}

_PREFERENCE_MARKERS: dict[str, tuple[str, ...]] = {
    "minimal": ("minimal", "surgical", "smallest", "least"),
    "thorough": ("thorough", "comprehensive", "complete", "exhaustive"),
    "fast": ("quick", "quickly", "fast", "asap", "urgent"),
    "careful": ("careful", "safe", "cautious", "conservative"),
}

_VAGUE_TERMS = (
    "something",
    "the thing",
    "stuff",
    "somehow",
    "appropriately",
    "whatever",
    "some things",
    "etc",
    "and so on",
    "as needed",
    "better",
)

_PRIORITY_MARKERS: dict[Priority, tuple[str, ...]] = {
    Priority.CRITICAL: ("critical", "emergency", "immediately", "asap", "urgent", "right now"),
    Priority.HIGH: ("important", "high priority", "soon", "priority"),
    Priority.LOW: ("low priority", "when you can", "no rush", "eventually"),
    Priority.BACKGROUND: ("whenever", "someday", "background"),
}

_CONFIDENCE_SCORE = {
    InterpretationConfidence.HIGH: 0.9,
    InterpretationConfidence.MEDIUM: 0.6,
    InterpretationConfidence.LOW: 0.3,
    InterpretationConfidence.UNKNOWN: 0.15,
}


class Interpreter(Protocol):
    """The understanding seam: any strategy turning a raw request into an IntentAnalysis."""

    version: str

    def interpret(self, request: IntentRequest, *, now: str) -> IntentAnalysis: ...


class DeterministicInterpreter:
    """The constitutional default: deterministic, evidence-based understanding."""

    version = INTERPRETER_VERSION

    def interpret(self, request: IntentRequest, *, now: str = "") -> IntentAnalysis:
        raw = request.raw_request
        text = raw.strip()
        lowered = text.lower()
        trace: list[str] = []

        objective = self._objective(text, lowered)
        domain, domain_evidence = self._domain(lowered)
        constraints = self._constraints(lowered)
        preferences = self._preferences(lowered)
        priority = self._priority(request, lowered)
        ambiguities = self._ambiguities(objective, lowered)
        missing = self._missing(objective, domain)
        trace.append(f"objective='{objective}'; domain={domain.value if domain else 'unknown'}")

        clarifications = self._clarifications(request.identity, ambiguities, missing)
        interaction_required = bool(clarifications)
        confidence = self._confidence(objective, domain, ambiguities, missing)
        resolved = not interaction_required
        trace.append(
            f"clarifications={len(clarifications)}; interaction_required={interaction_required}; "
            f"confidence={confidence.level.value}"
        )

        correlation = request.correlation_identifier or request.identity
        goal = None
        if resolved:
            goal = self._build_goal(
                request,
                objective,
                domain or Domain.SOFTWARE,
                priority,
                constraints,
                confidence.level,
                correlation,
            )

        intent = Intent(
            identity=request.identity,
            correlation=Correlation(correlation_identifier=correlation),
            raw_request=raw,
            modality=request.modality,
            detected_intent=objective,
            confidence=confidence.level,
            ambiguity=tuple(ambiguities),
            clarification_requests=tuple(c.model_dump(mode="json") for c in clarifications),
            missing_information=tuple(missing),
            detected_domain=domain,
            priority_estimate=priority,
            assumptions=(),
            interpretation_rationale=self._rationale(objective, domain, interaction_required),
            source=dict(request.source) if request.source is not None else None,
            resolved_goal_ref=(
                Reference(target_type="goal", identifier=goal.identity) if goal else None
            ),
        )

        analysis = IntentAnalysis(
            identity="",
            correlation_identifier=correlation,
            interpreter_version=self.version,
            intent=intent,
            goal=goal,
            clarifications=tuple(clarifications),
            confidence=confidence,
            interaction_required=interaction_required,
            resolved=resolved,
            operator_preferences=preferences,
            reasoning_trace=tuple(trace),
            declared_steps=self._declared_steps(text),
            timestamp=now,
        )
        return analysis.model_copy(update={"identity": ids.analysis_id(request, self.version)})

    # -- interpretation steps ----------------------------------------------- #

    def _objective(self, text: str, lowered: str) -> str:
        for prefix in _IMPERATIVE_PREFIXES:
            if lowered.startswith(prefix):
                return text[len(prefix) :].strip(" ,.:;").rstrip(".") or text
        return text.rstrip(".")

    def _domain(self, lowered: str) -> tuple[Domain | None, list[str]]:
        scores: dict[Domain, int] = {}
        evidence: list[str] = []
        for domain, tokens in _DOMAIN_SIGNALS.items():
            hits = [t for t in tokens if t in lowered]
            if hits:
                scores[domain] = len(hits)
                evidence.append(f"{domain.value}:{sorted(hits)}")
        if not scores:
            return None, evidence
        if lowered.startswith(("document ", "write ", "draft ")) and Domain.WRITING in scores:
            return Domain.WRITING, evidence
        top = max(scores.values())
        chosen = next(d for d in _DOMAIN_SIGNALS if scores.get(d, 0) == top)
        return chosen, evidence

    def _constraints(self, lowered: str) -> tuple[Constraint, ...]:
        found: list[Constraint] = []
        for kind, markers in _CONSTRAINT_MARKERS.items():
            hit = next((m for m in markers if m in lowered), None)
            if hit is not None:
                found.append(Constraint(kind=kind, detail={"marker": hit.strip()}))
        return tuple(found)

    def _preferences(self, lowered: str) -> dict[str, str]:
        prefs: dict[str, str] = {}
        for name, markers in _PREFERENCE_MARKERS.items():
            hit = next((m for m in markers if m in lowered), None)
            if hit is not None:
                prefs[name] = hit
        return prefs

    def _priority(self, request: IntentRequest, lowered: str) -> Priority:
        if request.provided_priority:
            try:
                return Priority(request.provided_priority)
            except ValueError:
                pass
        for priority, markers in _PRIORITY_MARKERS.items():
            if any(m in lowered for m in markers):
                return priority
        return Priority.MEDIUM

    def _ambiguities(self, objective: str, lowered: str) -> list[dict[str, object]]:
        found: list[dict[str, object]] = []
        vague = [t for t in _VAGUE_TERMS if t in lowered]
        if vague:
            found.append({"kind": "vague_terms", "detail": sorted(vague)})
        if len(objective.split()) < 3:
            found.append(
                {"kind": "underspecified", "detail": "the request is too short to be sure"}
            )
        words = objective.split()
        if (
            not found
            and len(words) <= 4
            and words
            and words[0].lower() in {"fix", "improve", "update", "make"}
        ):
            found.append(
                {
                    "kind": "acceptance_unspecified",
                    "detail": "no specific behavior or completion condition was stated",
                }
            )
        return found

    def _missing(self, objective: str, domain: Domain | None) -> list[str]:
        missing: list[str] = []
        words = objective.split()
        if len(words) < 2:
            missing.append("target: no clear subject/deliverable was stated")
        if domain is None:
            missing.append("domain: could not determine the kind of work")
        return missing

    def _clarifications(
        self, base: str, ambiguities: list[dict[str, object]], missing: list[str]
    ) -> tuple[ClarificationRequest, ...]:
        out: list[ClarificationRequest] = []
        for i, amb in enumerate(ambiguities):
            question = (
                "What specific behavior or outcome should change, and what would count as done?"
                if str(amb.get("kind"))
                in {"vague_terms", "underspecified", "acceptance_unspecified"}
                else f"Could you clarify the {amb.get('kind')} in your request?"
            )
            out.append(
                ClarificationRequest(
                    identity=f"clr-{base}-a{i}",
                    kind=ClarificationKind.AMBIGUITY,
                    subject=str(amb.get("kind")),
                    question=question,
                    reason=f"detected {amb.get('kind')}: {amb.get('detail')}",
                )
            )
        for i, item in enumerate(missing):
            field_name = item.split(":", 1)[0]
            out.append(
                ClarificationRequest(
                    identity=f"clr-{base}-m{i}",
                    kind=ClarificationKind.MISSING_INFORMATION,
                    subject=field_name,
                    question=f"Please provide the {field_name} for this request.",
                    reason=item,
                )
            )
        return tuple(out[:3])

    def _confidence(
        self,
        objective: str,
        domain: Domain | None,
        ambiguities: list[dict[str, object]],
        missing: list[str],
    ) -> IntentConfidence:
        factors = [
            f"objective_words={len(objective.split())}",
            f"domain={'detected' if domain else 'unknown'}",
            f"ambiguities={len(ambiguities)}",
            f"missing={len(missing)}",
        ]
        if ambiguities or missing:
            level = InterpretationConfidence.LOW
        elif domain is not None and len(objective.split()) >= 3:
            level = InterpretationConfidence.HIGH
        else:
            level = InterpretationConfidence.MEDIUM
        return IntentConfidence(level=level, score=_CONFIDENCE_SCORE[level], factors=tuple(factors))

    def _build_goal(
        self,
        request: IntentRequest,
        objective: str,
        domain: Domain,
        priority: Priority,
        constraints: tuple[Constraint, ...],
        confidence_level: InterpretationConfidence,
        correlation: str,
    ) -> Goal:
        return Goal(
            identity=f"goal-{request.identity}",
            outcome=objective,
            domain=domain,
            priority=priority,
            confidence=confidence_level,
            constraints=constraints,
            scope=Scope(),
            correlation=Correlation(correlation_identifier=correlation),
            source=dict(request.source) if request.source is not None else None,
            rationale=f"resolved from operator request '{request.identity}' (interpreter v{self.version})",
        )

    def _rationale(self, objective: str, domain: Domain | None, interaction_required: bool) -> str:
        if interaction_required:
            return f"understood objective '{objective}' but require clarification before producing a Goal"
        return f"understood objective '{objective}' in domain {domain.value if domain else 'software'}; resolved to a Goal"

    def _declared_steps(self, text: str) -> tuple[dict[str, object], ...]:
        """Capture an explicit first/then sequence without inventing a decomposition."""
        # ponytail: handles only literal first/then phrasing; broaden after a separately evaluated parser exists.
        match = re.search(
            r"\bfirst\b(.*?)(?:[,;]\s*|\s+)then\s+(.+)", text, re.IGNORECASE | re.DOTALL
        )
        if match is None:
            return ()
        before = text[: match.start()].strip(" .;,")
        first_clause = match.group(1).strip(" .;,")
        if (
            not first_clause
            or re.fullmatch(r"(?:it|this|that|the\s+\w+)", first_clause, re.IGNORECASE)
            or re.fullmatch(
                r"(?:change|modify|update|implement|fix|add)\s+(?:the\s+)?(?:function|it|this|that)",
                first_clause,
                re.IGNORECASE,
            )
        ):
            sentences = re.split(r"(?<=[.!?])\s+", before)
            candidate = sentences[-1] if sentences else before
            if re.fullmatch(
                r"(?:implement|change|add|write|test|modify|update|fix)\s+(?:it|this|that|the\s+\w+)",
                candidate.strip(" .;,"),
                re.IGNORECASE,
            ):
                candidate = sentences[-2] if len(sentences) > 1 else before
                if " and " in candidate.lower():
                    candidate = re.split(r"\s+and\s+", candidate, maxsplit=1, flags=re.IGNORECASE)[
                        0
                    ]
            first_clause = candidate
        elif first_clause.lower().endswith(("implement", "change", "add", "write", "test")):
            first_clause = before
        first_clause = first_clause.strip(" .;,")
        follow_up = re.split(r"[.!?]\s+", match.group(2), maxsplit=1)[0].strip(" .;,")
        independent = "independently" in match.group(2).lower()
        clauses = (
            [part.strip(" .;,") for part in re.split(r"\s+and\s+", follow_up)]
            if independent
            else [follow_up]
        )
        objectives = [first_clause, *clauses]
        objectives = [objective for objective in objectives if objective]
        if len(objectives) < 2:
            return ()
        steps: list[dict[str, object]] = []
        for index, objective in enumerate(objectives):
            steps.append(
                {
                    "key": f"step-{index + 1}",
                    "objective": objective,
                    "depends_on": ["step-1"]
                    if independent and index > 0
                    else ([f"step-{index}"] if index else []),
                }
            )
        return tuple(steps)
