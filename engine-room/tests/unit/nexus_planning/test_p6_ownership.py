"""P6 constitutional ownership — Planning consumes the EngineeringStrategy but performs no reasoning.

Proves the P6 success criteria on source and behavior: Planning performs no engineering reasoning,
no estimation, no policy evaluation, and no runtime recommendation; it *consumes* the Strategy's
already-decided postures; and each constitutional owner owns exactly one responsibility.
"""

from __future__ import annotations

import ast
from pathlib import Path

from nexus_core.contracts.enums import ApprovalTaxonomy, CoordinationModel, RetryBehavior
from nexus_infra import build_infrastructure
from nexus_planning import (
    PlanningRequest,
    WorkItemSpec,
    build_planning,
    strategy_hints,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _sources(package: str):
    directory = _REPO_ROOT / package
    return [p for p in directory.rglob("*.py") if "__pycache__" not in p.parts]


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


# -- source guardrails: Planning consumes, never reasons --------------------- #


def test_planning_performs_no_engineering_reasoning() -> None:
    # It may reference EngineeringStrategy (consume) and import nexus_engineering.model, but must
    # NOT invoke the reasoner/engine or construct a Strategy.
    for path in _sources("nexus_planning"):
        text = path.read_text(encoding="utf-8")
        for banned in ("EngineeringIntelligence", "DeterministicReasoner", "Reasoner"):
            assert banned not in text, f"{path.name} references {banned} — Planning must not reason"
        for module in _imported_modules(path):
            assert module not in ("nexus_engineering.engine", "nexus_engineering.reasoner"), (
                f"{path.name} imports EI internals {module}"
            )


def test_planning_performs_no_estimation() -> None:
    for path in _sources("nexus_planning"):
        for module in _imported_modules(path):
            assert not module.startswith("nexus_estimation"), f"{path.name} imports {module}"
        text = path.read_text(encoding="utf-8")
        for t in ("EstimationReport", "ComplexityEstimate", "EstimationEngine"):
            assert t not in text, f"{path.name} references estimation type {t}"


def test_planning_performs_no_policy_evaluation() -> None:
    for path in _sources("nexus_planning"):
        text = path.read_text(encoding="utf-8")
        assert "PolicyDecision" not in text, f"{path.name} references PolicyDecision"
        for module in _imported_modules(path):
            assert not module.startswith("nexus_policy"), f"{path.name} imports {module}"


def test_planning_performs_no_runtime_recommendation() -> None:
    # Planning carries EI's runtime *capability preferences* (not providers); it imports no runtime.
    for path in _sources("nexus_planning"):
        for module in _imported_modules(path):
            assert not module.startswith("nexus_runtime"), f"{path.name} imports runtime {module}"


def test_each_owner_owns_one_responsibility() -> None:
    # Intent performs no planning; EI performs no planning (they never import nexus_planning).
    for package in ("nexus_intent", "nexus_engineering"):
        for path in _sources(package):
            for module in _imported_modules(path):
                assert not module.startswith("nexus_planning"), (
                    f"{package}/{path.name} imports {module}"
                )


# -- behavior: Planning consumes the Strategy's postures --------------------- #


def _strategy():
    from nexus_core.contracts.base import Correlation
    from nexus_core.contracts.enums import Domain, InterpretationConfidence, Priority
    from nexus_core.domain.goal import Goal, Scope
    from nexus_engineering import build_engineering
    from nexus_estimation import build_estimation
    from nexus_policy import build_policy

    infra = build_infrastructure()
    goal = Goal(
        identity="g",
        outcome="fix the failing auth bug in production",
        domain=Domain.SOFTWARE,
        priority=Priority.HIGH,
        confidence=InterpretationConfidence.MEDIUM,
        constraints=(),
        scope=Scope(),
        correlation=Correlation(correlation_identifier="cor"),
    )
    eng = build_engineering(infra, now=lambda: "t")
    est = build_estimation(infra, now=lambda: "t")
    pol = build_policy(infra, now=lambda: "t")
    return goal, eng.strategize_for_goal(
        goal, estimation_engine=est.engine, policy_engine=pol.engine
    )


def test_strategy_hints_map_every_posture() -> None:
    _, strategy = _strategy()
    hints = strategy_hints(strategy)
    assert isinstance(hints["coordination_hint"], CoordinationModel)
    assert isinstance(hints["approval_hint"], ApprovalTaxonomy)
    assert isinstance(hints["retry_hint"], RetryBehavior)
    assert "rigor" in hints["validation_policy"]
    assert hints["runtime_policy"]["capabilities"]
    assert hints["engineering_strategy_ref"].identifier == strategy.identity


def test_planning_consumes_strategy_instead_of_deriving() -> None:
    goal, strategy = _strategy()
    infra = build_infrastructure()
    ctx = build_planning(infra)
    req = PlanningRequest(
        work_items=(WorkItemSpec(key="w", objective="fix", capability_requirements=("c",)),)
    )
    result = ctx.service.plan(goal, req, engineering_strategy=strategy)
    es = result.execution_strategy
    # postures now come from EI, not from topology derivation
    assert es.coordination.value == strategy.execution_style.selection[0]
    assert dict(es.validation_policy)["rigor"] == strategy.validation_rigor.selection[0]
    assert dict(es.runtime_policy)["capabilities"]
    assert result.plan.identity  # decomposition still owned by Planning


def test_operator_authored_path_still_works_without_a_strategy() -> None:
    # Backward compatibility: no strategy → existing derivation applies unchanged.
    goal, _ = _strategy()
    ctx = build_planning(build_infrastructure())
    req = PlanningRequest(
        work_items=(WorkItemSpec(key="w", objective="fix", capability_requirements=("c",)),)
    )
    result = ctx.service.plan(goal, req)
    assert result.execution_strategy.coordination in tuple(CoordinationModel)
    assert dict(result.execution_strategy.runtime_policy) == {}
