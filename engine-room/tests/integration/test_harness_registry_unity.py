"""P17 regression — the Harness Registry is one source of truth per wired context (INV-36).

Two composition roots (``nexus_workflows.pipeline.PipelineBuilder`` and
``nexus_execution.actuation.build_execution_actuation``) call ``nexus_runtime.build_runtime``
without forwarding the ``harness_registry`` they had already built for Orchestration/Actuation,
so ``build_runtime`` silently default-constructed a second, unsynchronized
``InMemoryHarnessRegistry``. A descriptor registered on the Orchestration/Actuation side (candidate
discovery, INV-37) was then invisible to the Runtime Manager's selection funnel and vice versa —
the exact split INV-36 ("no other registry duplicates it") exists to prevent. Fixed by threading the
same registry instance through both call sites; these tests pin that down.
"""

from __future__ import annotations

from nexus_runtime_claude import ClaudeRuntimeAdapter, StubClaudeInvoker
from nexus_workflows.pipeline import PipelineBuilder
from tests.unit.nexus_execution.actuation.fixtures import wired


def test_pipeline_builder_shares_one_harness_registry_with_runtime() -> None:
    pipeline = PipelineBuilder().build()

    assert pipeline.harness_registry is pipeline.runtime.harness_registry

    descriptor = ClaudeRuntimeAdapter(invoker=StubClaudeInvoker()).descriptor()
    pipeline.harness_registry.register(descriptor)

    assert descriptor in pipeline.runtime.harness_registry.list_all()
    assert descriptor in pipeline.orchestration.harness_registry.list_all()


def test_execution_actuation_shares_one_harness_registry_with_runtime() -> None:
    _infra, ctx = wired()

    assert ctx.harness_registry is ctx.runtime.harness_registry
    # build_execution_actuation registers the injected adapter's descriptor on ctx.harness_registry
    # (candidate discovery, INV-37) — it must be visible through the Runtime Manager's own view too.
    registered = ctx.harness_registry.list_all()
    assert registered
    visible = ctx.runtime.harness_registry.list_all()
    assert all(descriptor in visible for descriptor in registered)
