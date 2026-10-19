"""Deterministic, explainable relevance selection over grounding facts (no AI, no embeddings).

This is P9's **Context Selection**: given the grounding artifacts, decide *which* ADRs,
contracts, invariants, architecture docs, modules, packages, files, prior executions, and
knowledge items are relevant to the Goal — and record *why* each one was included or omitted.

The rule is a pure function of recorded facts:

1. **Criteria.** The selection criteria are the EngineeringStrategy's *context objectives*
   (P5) when present, else keywords derived from the Goal (outcome, domain, in-scope items).
2. **Candidates.** Every artifact the RepositoryProfile / ExecutionHistoryProfile / Knowledge
   expose is a candidate, each with a base priority per artifact kind and a stated relationship.
3. **Verdict.** A candidate is *selected* when its identity or relationship matches a criterion
   keyword (knowledge, already relevance-filtered by its retrieval seam, is admitted by
   default); everything else is *omitted with a reason*. Selected sets are then capped per kind
   (minimal-complete context, doc 03) — overflow is omitted with an explicit rank reason.

There is no LLM, no semantic search, no embedding, and no floating-point score — identical
grounding always yields an identical selection and identical ordering.
"""

from __future__ import annotations

from dataclasses import dataclass

from nexus_context.grounding.model import (
    GroundingInputs,
    GroundingSelection,
    SelectionRecord,
)


@dataclass(frozen=True, slots=True)
class _Candidate:
    """One grounding artifact under consideration (base priority + the text it matches on)."""

    artifact_type: str
    identifier: str
    source: str
    relationship: str
    base: int
    match_text: str


# Base relevance per artifact kind (higher = more likely to matter to a governed engineering
# goal). Selection is still keyword-gated; this only orders and caps what matched.
_BASE_PRIORITY: dict[str, int] = {
    "adr": 90,
    "contract": 88,
    "invariant": 86,
    "architecture_doc": 70,
    "module": 60,
    "package": 58,
    "file": 50,
    "prior_execution": 40,
    "knowledge": 45,
}

# Per-kind cap — "do not include everything" (doc 03 *Minimal Complete Context*).
_CAP: dict[str, int] = {
    "adr": 8,
    "contract": 8,
    "invariant": 8,
    "architecture_doc": 6,
    "module": 12,
    "package": 12,
    "file": 10,
    "prior_execution": 8,
    "knowledge": 12,
}

_MATCH_BONUS = 100

_STOPWORDS = frozenset(
    {
        "the",
        "and",
        "for",
        "with",
        "that",
        "this",
        "into",
        "from",
        "have",
        "will",
        "make",
        "add",
        "fix",
        "use",
        "get",
        "set",
        "run",
        "new",
        "all",
        "any",
        "not",
        "are",
        "was",
        "can",
        "out",
        "its",
        "our",
        "per",
        "via",
        "how",
        "what",
        "when",
        "should",
        "must",
        "need",
        "want",
        "then",
        "than",
        "them",
        "they",
        "your",
    }
)


def _tokenize(text: str) -> list[str]:
    """Lowercase alphanumeric tokens (>=3 chars, non-stopword) — the keyword atoms."""
    token = []
    tokens: list[str] = []
    for ch in text.lower():
        if ch.isalnum():
            token.append(ch)
        elif token:
            tokens.append("".join(token))
            token = []
    if token:
        tokens.append("".join(token))
    return [t for t in tokens if len(t) >= 3 and t not in _STOPWORDS]


class GroundingSelector:
    """Selects the relevant grounding artifacts deterministically, explaining every verdict."""

    def __init__(self, *, caps: dict[str, int] | None = None) -> None:
        self._caps = caps or _CAP

    def select(self, inputs: GroundingInputs) -> GroundingSelection:
        objectives = self._objectives(inputs)
        keywords = self._keywords(inputs, objectives)
        candidates = list(self._candidates(inputs))

        # Verdict per candidate (keyword-gated; knowledge admitted by default).
        matched: list[SelectionRecord] = []
        omitted: list[SelectionRecord] = []
        for cand in candidates:
            hit = self._matches(cand, keywords)
            if hit or cand.artifact_type == "knowledge":
                priority = cand.base + (_MATCH_BONUS if hit else 0)
                reason = (
                    f"matches criterion '{hit}'"
                    if hit
                    else "admitted: knowledge is pre-filtered by its retrieval seam"
                )
                matched.append(self._record(cand, priority, True, reason))
            else:
                omitted.append(
                    self._record(cand, cand.base, False, "no objective/goal keyword matched")
                )

        selected = self._apply_caps(matched, omitted)
        selected.sort(key=lambda r: (-r.priority, r.artifact_type, r.identifier))
        omitted.sort(key=lambda r: (-r.priority, r.artifact_type, r.identifier))
        omitted.extend(self._absent_sources(inputs))
        return GroundingSelection(
            objectives=tuple(objectives),
            keywords=tuple(keywords),
            selected=tuple(selected),
            omitted=tuple(omitted),
        )

    # -- criteria ------------------------------------------------------------ #

    @staticmethod
    def _objectives(inputs: GroundingInputs) -> list[str]:
        strategy = inputs.engineering_strategy
        if strategy is None:
            return []
        return list(strategy.context_objectives.selection)

    def _keywords(self, inputs: GroundingInputs, objectives: list[str]) -> list[str]:
        goal = inputs.goal
        text_parts = [goal.outcome, goal.domain.value, *goal.scope.included, *objectives]
        if goal.success_definition:
            text_parts.append(goal.success_definition)
        seen: dict[str, None] = {}
        for part in text_parts:
            for token in _tokenize(part):
                seen.setdefault(token, None)
        return list(seen)

    # -- candidates ---------------------------------------------------------- #

    def _candidates(self, inputs: GroundingInputs) -> list[_Candidate]:
        out: list[_Candidate] = []
        out.extend(self._repository_candidates(inputs))
        out.extend(self._history_candidates(inputs))
        out.extend(self._knowledge_candidates(inputs))
        return out

    def _repository_candidates(self, inputs: GroundingInputs) -> list[_Candidate]:
        profile = inputs.repository_profile
        if profile is None or not profile.exists:
            return []
        c = profile.constitutional
        out: list[_Candidate] = []
        out += [
            self._cand("adr", f, "repository", "constitutional ADR in repository")
            for f in c.adr_files
        ]
        out += [
            self._cand("contract", f, "repository", "frozen contract in repository")
            for f in c.contract_files
        ]
        out += [
            self._cand("invariant", f, "repository", "architectural invariant in repository")
            for f in c.invariant_files
        ]
        out += [
            self._cand("architecture_doc", f, "repository", "architecture document in repository")
            for f in profile.documentation.architecture_docs
        ]
        out += [
            self._cand("module", n, "repository", "module in the module graph")
            for n in profile.module_graph.nodes
        ]
        out += [
            self._cand("package", p, "repository", "package in the repository")
            for p in profile.packages.packages
        ]
        keywords = set(_tokenize(inputs.goal.outcome))
        broad = {
            "cli",
            "test",
            "tests",
            "python",
            "repository",
            "repo",
            "code",
            "file",
            "files",
            "option",
        }
        terms = keywords - broad
        paths = set(profile.files)
        relevant = {path for path in paths if terms.intersection(_tokenize(path.replace("_", " ")))}
        request_terms = set(_tokenize(inputs.goal.outcome))
        if inputs.goal.domain.value == "software" and request_terms.intersection(
            {"cli", "command", "commands", "option", "version"}
        ):
            relevant.update(
                path
                for path in paths
                if path.rsplit("/", 1)[-1]
                in {"main.py", "cli.py", "__main__.py", "main.ts", "index.js"}
            )
        if inputs.goal.domain.value == "software" and not relevant:
            relevant.update(profile.structure.entry_points)
        if inputs.goal.domain.value == "software":
            source_stems = {
                path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
                for path in relevant
                if path.startswith("src/")
            }
            for path in paths:
                name = path.rsplit("/", 1)[-1]
                if path.startswith("tests/") and name.startswith("test_"):
                    stem = name.removeprefix("test_").rsplit(".", 1)[0]
                    if stem in source_stems:
                        relevant.add(path)
        for path in sorted(relevant)[:50]:
            out.append(
                self._cand(
                    "file", path, "repository", "file path in the profiled repository inventory"
                )
            )
        return out

    def _history_candidates(self, inputs: GroundingInputs) -> list[_Candidate]:
        history = inputs.history_profile
        if history is None or not history.available:
            return []
        out: list[_Candidate] = []
        for episode in history.executions:
            flags = []
            if episode.validated:
                flags.append("validated")
            if episode.recovered:
                flags.append("recovered")
            if episode.reflected:
                flags.append("reflected")
            rel = "prior execution" + (f" ({', '.join(flags)})" if flags else "")
            out.append(
                self._cand(
                    "prior_execution", episode.correlation_identifier, "execution_history", rel
                )
            )
        return out

    def _knowledge_candidates(self, inputs: GroundingInputs) -> list[_Candidate]:
        out: list[_Candidate] = []
        for item in inputs.knowledge:
            summary = item.understanding[:80].replace("\n", " ")
            domain = item.domain.value if item.domain is not None else "general"
            rel = f"{item.type.value} knowledge [{domain}]: {summary}"
            out.append(self._cand("knowledge", item.identity, "knowledge", rel))
        return out

    @staticmethod
    def _cand(artifact_type: str, identifier: str, source: str, relationship: str) -> _Candidate:
        # Repository artifacts match on identity only (their relationship is a generic label);
        # knowledge / prior executions also match on relationship, which carries their meaning.
        semantic = artifact_type in ("knowledge", "prior_execution")
        match_text = f"{identifier} {relationship}" if semantic else identifier
        return _Candidate(
            artifact_type=artifact_type,
            identifier=identifier,
            source=source,
            relationship=relationship,
            base=_BASE_PRIORITY[artifact_type],
            match_text=match_text.lower(),
        )

    # -- verdict helpers ----------------------------------------------------- #

    @staticmethod
    def _matches(cand: _Candidate, keywords: list[str]) -> str:
        """Return the first matching keyword (truthy) or '' — matched against the candidate text."""
        if cand.artifact_type == "file" and cand.identifier.rsplit("/", 1)[-1] in {
            "main.py",
            "cli.py",
            "__main__.py",
            "main.ts",
            "index.js",
        }:
            for keyword in keywords:
                if keyword in {"cli", "command", "commands", "option", "version"}:
                    return keyword
        for keyword in keywords:
            if keyword in cand.match_text:
                return keyword
        return ""

    @staticmethod
    def _record(cand: _Candidate, priority: int, selected: bool, reason: str) -> SelectionRecord:
        return SelectionRecord(
            artifact_type=cand.artifact_type,
            identifier=cand.identifier,
            source=cand.source,
            relationship=cand.relationship,
            priority=priority,
            selected=selected,
            reason=reason,
        )

    def _apply_caps(
        self, matched: list[SelectionRecord], omitted: list[SelectionRecord]
    ) -> list[SelectionRecord]:
        """Keep the top-K per kind (minimal complete context); demote overflow to omitted."""
        by_kind: dict[str, list[SelectionRecord]] = {}
        for record in matched:
            by_kind.setdefault(record.artifact_type, []).append(record)
        kept: list[SelectionRecord] = []
        for kind, records in by_kind.items():
            records.sort(key=lambda r: (-r.priority, r.identifier))
            cap = self._caps.get(kind, len(records))
            kept.extend(records[:cap])
            for rank, record in enumerate(records[cap:], start=cap + 1):
                omitted.append(
                    record.model_copy(
                        update={
                            "selected": False,
                            "reason": f"below relevance cap for {kind} (rank {rank} of {len(records)})",
                        }
                    )
                )
        return kept

    @staticmethod
    def _absent_sources(inputs: GroundingInputs) -> list[SelectionRecord]:
        """Explain each grounding source that contributed nothing because it was absent."""
        out: list[SelectionRecord] = []
        checks = (
            (
                inputs.repository_profile is None,
                "repository",
                "repository",
                "no repository profile provided",
            ),
            (
                inputs.history_profile is None,
                "execution_history",
                "execution_history",
                "no execution-history profile provided",
            ),
            (
                inputs.engineering_strategy is None,
                "engineering_strategy",
                "engineering_strategy",
                "no engineering strategy provided; selection fell back to goal-derived keywords",
            ),
            (not inputs.knowledge, "knowledge", "knowledge", "no knowledge items provided"),
        )
        for absent, artifact_type, source, reason in checks:
            if absent:
                out.append(
                    SelectionRecord(
                        artifact_type=artifact_type,
                        identifier="(source absent)",
                        source=source,
                        relationship="grounding source not supplied",
                        priority=0,
                        selected=False,
                        reason=reason,
                    )
                )
        return out
