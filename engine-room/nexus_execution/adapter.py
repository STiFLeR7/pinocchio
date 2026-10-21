"""The Runtime Adapter contract — the concrete materialization of doc 03's nine concerns.

Doc 03 defines the adapter as a *conceptual* contract ("no interface signature, no method
list, no algorithm"). This module makes it a concrete Python :class:`~typing.Protocol` so
the generic :class:`~nexus_execution.engine.ExecutionEngine` can drive **any** provider
identically. It coins no new lifecycle state or event and adds no tenth concern; each
member maps 1:1 onto a concern A-I of doc 03 §2.

All provider-specific code lives behind an *implementation* of this protocol (e.g.
``nexus_runtime_claude``); the engine and RM core import no implementation and branch on no
provider (doc 03 §3 litmus). The adapter is a **driver**, never a decision-maker (doc 03 §6).
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from nexus_core.contracts.base import Reference, Struct
from nexus_core.domain.work_package import WorkPackage
from nexus_core.registries.interfaces import HarnessDescriptor
from nexus_execution.signals import RuntimeSignal


@dataclass(frozen=True, slots=True)
class AdapterConfig:
    """RM-rendered, declarative configuration handed to the adapter (concern B).

    Carries secret *references* only, never values (doc 17 §3): the value lives in ``.env``
    and is injected at configure-time by reference. ``working_dir`` / ``env_keys`` /
    ``isolation_profile`` are echoed back (secret-free) for the ``runtime.prepared`` telemetry.
    """

    working_dir: str
    env_keys: tuple[str, ...] = ()
    secret_refs: tuple[Reference, ...] = ()
    isolation_profile: str = "process"
    limits: Struct = field(default_factory=dict)
    metadata: Struct = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ConfiguredRuntime:
    """The adapter's secret-free acknowledgement of configuration (concern B result)."""

    runtime_identity: str
    isolation_profile: str
    working_dir: str
    env_keys: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class TeardownReport:
    """The result of adapter cleanup (concern I). ``ok=False`` ⇒ a typed teardown error."""

    ok: bool
    detail: str | None = None


class ExecutionControl:
    """Cooperative cancel/timeout signal the engine passes into ``execute`` (concern G).

    Cancellation is cooperative: the adapter checks :attr:`cancelled` between signals and
    stops gracefully. The engine *also* enforces it — it stops consuming once cancelled and
    synthesizes a terminal, so an uncooperative adapter cannot run past a cancel (doc 09,
    graceful-then-forced). ``deadline_steps`` bounds the number of consumed signals before a
    timeout fires — a deterministic, clock-free model of doc 10's wire/inactivity bound
    (production uses a wall-clock deadline; the semantics are identical).
    """

    def __init__(self, *, deadline_steps: int | None = None) -> None:
        self._cancelled = False
        self.deadline_steps = deadline_steps

    @property
    def cancelled(self) -> bool:
        """Whether a cancellation has been requested."""
        return self._cancelled

    def cancel(self) -> None:
        """Request cancellation (idempotent)."""
        self._cancelled = True


@runtime_checkable
class RuntimeAdapter(Protocol):
    """The single driver contract every runtime satisfies (doc 03 §2, concerns A-I)."""

    def descriptor(self) -> HarnessDescriptor:
        """A — Advertise: the Registry descriptor (identity, version, capabilities)."""
        ...

    def configure(self, config: AdapterConfig) -> ConfiguredRuntime:
        """B — Configure: translate RM's declarative config into provider setup (secret-free)."""
        ...

    def execute(
        self,
        *,
        session_ref: Reference,
        work_package: WorkPackage,
        control: ExecutionControl,
    ) -> Iterator[RuntimeSignal]:
        """C/D/E/F/H — Start the runtime and yield ordered signals ending in a terminal."""
        ...

    def cleanup(self) -> TeardownReport:
        """I — Clean up: release processes/containers/workspaces/credential handles (doc 17)."""
        ...
