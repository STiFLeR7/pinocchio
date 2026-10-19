"""``nexus_execution`` — the minimal Execution Engine for the Runtime vertical slice.

The Execution Engine **performs** what the Runtime Manager **prepared** (doc 00 §1/§8):
given a ``Ready`` Runtime Session and a :class:`RuntimeAdapter`, it starts the runtime,
consumes the adapter's ordered signals, records canonical ``runtime.*`` events, honors
cancellation/timeout, collects artifacts by reference, maps failures onto the doc-11 error
model, runs cleanup, and returns an :class:`ExecutionResult` — reaching ``Destroyed``::

    … → Runtime Manager → Runtime Session (Ready) → Execution Engine → Runtime Adapter
        → Runtime → Execution Result

This package is **generic**: it imports no provider and branches on none. The concrete
:class:`RuntimeAdapter` protocol here is the materialization of doc 03's conceptual
nine-concern contract; provider-specific behavior lives only in an *implementation* of it
(e.g. ``nexus_runtime_claude``). Dependency direction:
``nexus_execution → {nexus_runtime, nexus_core, nexus_infra}`` — it consumes RM's Runtime
Session downstream and reuses the Phase 2 substrate without modifying it.
"""

from __future__ import annotations

from nexus_execution.adapter import (
    AdapterConfig,
    ConfiguredRuntime,
    ExecutionControl,
    RuntimeAdapter,
    TeardownReport,
)
from nexus_execution.composition import ExecutionContext, build_execution
from nexus_execution.engine import ExecutionEngine
from nexus_execution.errors import (
    ExecutionError,
    ExecutionStartupError,
    InfrastructureError,
    ProviderError,
    RuntimeTimeoutError,
    TeardownError,
    TransportError,
    UserCancellationError,
)
from nexus_execution.observability import ExecutionObservability
from nexus_execution.results import ExecutionResult
from nexus_execution.signals import (
    ArtifactSignal,
    OutputSignal,
    ProgressSignal,
    RuntimeSignal,
    StreamChannel,
    TerminalOutcome,
    TerminalSignal,
)

__version__ = "2.5.0"

__all__ = [
    "AdapterConfig",
    "ArtifactSignal",
    "ConfiguredRuntime",
    "ExecutionContext",
    "ExecutionControl",
    "ExecutionEngine",
    "ExecutionError",
    "ExecutionObservability",
    "ExecutionResult",
    "ExecutionStartupError",
    "InfrastructureError",
    "OutputSignal",
    "ProgressSignal",
    "ProviderError",
    "RuntimeAdapter",
    "RuntimeSignal",
    "RuntimeTimeoutError",
    "StreamChannel",
    "TeardownError",
    "TeardownReport",
    "TerminalOutcome",
    "TerminalSignal",
    "TransportError",
    "UserCancellationError",
    "build_execution",
]
