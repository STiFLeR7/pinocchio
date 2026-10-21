"""Intent composition — dependency-injection wiring for Intent Resolution.

Mirrors ``build_estimation`` / ``build_engineering``: it **reuses** the P1 substrate unchanged
(emitter = the infrastructure context, repository = a reused ``InMemoryRepository``, metrics = the
context's observability). Integration is additive DI only; no engine is modified. Durable
persistence is transparent over ``build_durable_infrastructure`` (ADR-007).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from nexus_infra import InfrastructureContext
from nexus_intent.engine import IntentResolution
from nexus_intent.interpreter import Interpreter
from nexus_intent.observability import IntentObservability
from nexus_intent.persistence import IntentRepositories, build_intent_repositories


@dataclass(frozen=True, slots=True)
class IntentContext:
    """The wired Intent-Resolution subsystem (immutable wiring, stateful engine + repository)."""

    infrastructure: InfrastructureContext
    repositories: IntentRepositories
    engine: IntentResolution


def build_intent(
    infrastructure: InfrastructureContext,
    *,
    interpreter: Interpreter | None = None,
    repositories: IntentRepositories | None = None,
    now: Callable[[], str] | None = None,
) -> IntentContext:
    """Wire an intent context over an infrastructure context; all parts overridable."""
    obs = infrastructure.observability
    resolved = repositories or build_intent_repositories(obs)
    engine = IntentResolution(
        interpreter,
        emitter=infrastructure,
        repositories=resolved,
        observability=IntentObservability(obs),
        now=now,
    )
    return IntentContext(infrastructure=infrastructure, repositories=resolved, engine=engine)
