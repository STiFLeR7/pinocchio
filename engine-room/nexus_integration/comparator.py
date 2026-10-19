"""Decision comparison by determinism class (ADR-008 §3.3) — the diff engine.

The comparator's verdict is a function of the decision's determinism class:

- **Deterministic** (rule/config/state-machine): exact equality. A difference is a real
  mismatch.
- **Probabilistic** (LLM/cognition): a **semantic hook only** — never exact-match
  enforcement (per ADR-004's determinism boundaries; applying exact-match to an LLM
  decision is a defect, ADR-008 §3.3). Without a hook the verdict is ``UNDETERMINED``
  (human adjudication), never a false ``MISMATCH``.
- **External-state**: **evidence-aware** — an injected predicate decides equivalence.

The strategy set is **extensible**: :class:`ComparatorRegistry` maps a determinism class
to a comparator and is overridable per owner. Comparison is a pure function → diff
generation is deterministic.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol, runtime_checkable

from nexus_core.contracts.base import Struct
from nexus_integration.model import DeterminismClass, DiffVerdict


@runtime_checkable
class Comparator(Protocol):
    """Classifies a legacy-vs-shadow pair into a verdict + explanatory detail (pure)."""

    def compare(self, legacy: Any, shadow: Any) -> tuple[DiffVerdict, Struct]: ...


class DeterministicComparator:
    """Exact equality for deterministic decisions (ADR-008 §3.3)."""

    def compare(self, legacy: Any, shadow: Any) -> tuple[DiffVerdict, Struct]:
        if legacy == shadow:
            return DiffVerdict.MATCH, {}
        return DiffVerdict.MISMATCH, {"reason": "values are not exactly equal"}


class ProbabilisticComparator:
    """Semantic comparison for non-deterministic decisions — never exact-match (ADR-008 §3.3).

    ``equivalence`` is an injected band/semantic hook: ``(legacy, shadow) -> bool``. With
    no hook the verdict is ``UNDETERMINED`` (route to human), never a false mismatch.
    """

    def __init__(self, equivalence: Callable[[Any, Any], bool] | None = None) -> None:
        self._equivalence = equivalence

    def compare(self, legacy: Any, shadow: Any) -> tuple[DiffVerdict, Struct]:
        if self._equivalence is None:
            return DiffVerdict.UNDETERMINED, {
                "reason": "no semantic comparator; human adjudication required"
            }
        if self._equivalence(legacy, shadow):
            return DiffVerdict.EQUIVALENT, {}
        return DiffVerdict.MISMATCH, {"reason": "outside the equivalence band"}


class ExternalStateComparator:
    """Evidence-aware comparison for decisions that depend on live external state.

    ``evidence`` is an injected predicate ``(legacy, shadow) -> bool`` that accounts for
    legitimate external-state drift (e.g. a live-git read); its absence defaults to
    equality, which callers override per owner.
    """

    def __init__(self, evidence: Callable[[Any, Any], bool] | None = None) -> None:
        self._evidence = evidence or (lambda legacy, shadow: legacy == shadow)

    def compare(self, legacy: Any, shadow: Any) -> tuple[DiffVerdict, Struct]:
        if self._evidence(legacy, shadow):
            return DiffVerdict.EQUIVALENT, {}
        return DiffVerdict.MISMATCH, {"reason": "evidence indicates a real divergence"}


class ComparatorRegistry:
    """An extensible map from determinism class to comparator (overridable per owner)."""

    def __init__(self, mapping: dict[DeterminismClass, Comparator] | None = None) -> None:
        self._by_class: dict[DeterminismClass, Comparator] = dict(mapping or {})

    def register(self, determinism_class: DeterminismClass, comparator: Comparator) -> None:
        """Override the comparator used for ``determinism_class``."""
        self._by_class[determinism_class] = comparator

    def for_class(self, determinism_class: DeterminismClass) -> Comparator:
        """The comparator for ``determinism_class`` (raises if none is registered)."""
        try:
            return self._by_class[determinism_class]
        except KeyError as exc:
            raise KeyError(f"no comparator registered for {determinism_class}") from exc


def default_comparators() -> ComparatorRegistry:
    """The default strategy set: exact / semantic-hook / evidence-aware by class (ADR-008 §3.3)."""
    return ComparatorRegistry(
        {
            DeterminismClass.DETERMINISTIC: DeterministicComparator(),
            DeterminismClass.PROBABILISTIC: ProbabilisticComparator(),  # UNDETERMINED until a hook is registered
            DeterminismClass.EXTERNAL_STATE: ExternalStateComparator(),
        }
    )
