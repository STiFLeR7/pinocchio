"""The Shell Runtime Adapter — all shell-specific behavior, and nothing generic.

A third implementation of the generic :class:`~nexus_execution.adapter.RuntimeAdapter`
protocol (doc 03). Unlike the model-backed Claude/Gemini adapters, a shell runtime has no
"assistant turn" or "tool use" vocabulary: it runs a command and surfaces stdout/stderr and
an exit code. That difference is confined entirely to *normalization* — the same nine
concerns, the same runtime-independent signals, so Planning/Orchestration/Harness/Runtime
Manager/Execution drive it identically (the Runtime abstraction is provider-agnostic).

* **A Advertise** — a ``RUNTIME`` descriptor advertising abstract capabilities (``05``);
* **B Configure** — echo RM's rendered config secret-free (``17`` §3);
* **C/D/E/F/H Execute** — render the Work Package into a shell command, drive the injected
  :class:`~nexus_runtime_shell.invoker.ShellInvoker`, and **semantically normalize** each raw
  shell event (stdout→output, stderr→output, produced file→artifact, exit→terminal);
* **I Clean up** — release the (stub or subprocess) session.

It contains **no business logic** (Milestone 3): it decides nothing, grades nothing, and maps
a non-zero exit onto the doc-11 error model via a FAILED terminal signal.
"""

from __future__ import annotations

from collections.abc import Iterator

from nexus_core.contracts.base import Reference
from nexus_core.contracts.enums import ResourceAvailability
from nexus_core.domain.work_package import WorkPackage
from nexus_core.registries.interfaces import HarnessCategory, HarnessDescriptor
from nexus_execution.adapter import (
    AdapterConfig,
    ConfiguredRuntime,
    ExecutionControl,
    TeardownReport,
)
from nexus_execution.errors import ProviderError
from nexus_execution.signals import (
    ArtifactSignal,
    OutputSignal,
    RuntimeSignal,
    StreamChannel,
    TerminalOutcome,
    TerminalSignal,
)
from nexus_runtime_shell.invoker import (
    RawShellEvent,
    RawShellKind,
    ShellInvoker,
    StubShellInvoker,
)

SHELL_RUNTIME_IDENTITY = "shell"
SHELL_CAPABILITIES = ("command_execution", "code_generation", "file_write")
_ARTIFACT_TARGET_TYPE = "artifact"


class ShellRuntimeAdapter:
    """Drives a local shell behind the generic adapter contract (all provider logic here)."""

    def __init__(
        self,
        *,
        invoker: ShellInvoker | None = None,
        identity: str = SHELL_RUNTIME_IDENTITY,
        version: str = "1",
    ) -> None:
        self._invoker = invoker or StubShellInvoker()
        self._identity = identity
        self._version = version
        self._working_dir = "."
        self._configured = False

    # -- A: Advertise -------------------------------------------------------- #

    def descriptor(self) -> HarnessDescriptor:
        """Advertise a ``RUNTIME`` descriptor with abstract, provider-independent capabilities."""
        return HarnessDescriptor(
            identity=self._identity,
            category=HarnessCategory.RUNTIME,
            version=self._version,
            advertised_capabilities=tuple(
                Reference(target_type="capability", identifier=c) for c in SHELL_CAPABILITIES
            ),
            availability=ResourceAvailability.AVAILABLE,
            health=ResourceAvailability.AVAILABLE,
            metadata={"provider": "shell"},
        )

    # -- B: Configure -------------------------------------------------------- #

    def configure(self, config: AdapterConfig) -> ConfiguredRuntime:
        """Translate RM's declarative config; echo it back secret-free (never values)."""
        self._working_dir = config.working_dir
        self._configured = True
        return ConfiguredRuntime(
            runtime_identity=self._identity,
            isolation_profile=config.isolation_profile,
            working_dir=config.working_dir,
            env_keys=config.env_keys,
        )

    # -- C/D/E/F/H: Execute -------------------------------------------------- #

    def execute(
        self,
        *,
        session_ref: Reference,
        work_package: WorkPackage,
        control: ExecutionControl,
    ) -> Iterator[RuntimeSignal]:
        """Render the Work Package into a command, drive the shell, normalize each event."""
        command = self._render_command(work_package)
        for raw in self._invoker.invoke(
            command=command, working_dir=self._working_dir, control=control
        ):
            yield self._normalize(raw, work_package)
            if raw.kind is RawShellKind.EXIT:
                return
        # Stream ended without an exit code — report an honest completion (doc 12).
        yield TerminalSignal(TerminalOutcome.COMPLETED, exit_status=0, detail="stream ended")

    def _normalize(self, raw: RawShellEvent, work_package: WorkPackage) -> RuntimeSignal:
        """Semantic normalization (doc 22 §3): raw shell event → runtime-independent signal."""
        if raw.kind is RawShellKind.STDOUT:
            return OutputSignal(channel=StreamChannel.STDOUT, text=raw.text + "\n")
        if raw.kind is RawShellKind.STDERR:
            return OutputSignal(channel=StreamChannel.STDERR, text=raw.text + "\n")
        if raw.kind is RawShellKind.ARTIFACT:
            identifier = self._artifact_identifier(raw, work_package)
            return ArtifactSignal(
                artifact_ref=Reference(target_type=_ARTIFACT_TARGET_TYPE, identifier=identifier),
                kind=raw.name or "file",
            )
        # RawShellKind.EXIT — a zero exit completes; any other exit is a doc-11 failure.
        if raw.exit_status == 0:
            return TerminalSignal(TerminalOutcome.COMPLETED, exit_status=0)
        fault = ProviderError(f"command exited {raw.exit_status}")
        return TerminalSignal(
            TerminalOutcome.FAILED,
            exit_status=raw.exit_status,
            detail=fault.detail,
            error_class=fault.error_class,
        )

    # -- I: Clean up --------------------------------------------------------- #

    def cleanup(self) -> TeardownReport:
        """Release the shell session; the stub holds no OS resource, so cleanup is trivial."""
        self._configured = False
        return TeardownReport(ok=True)

    # -- helpers ------------------------------------------------------------- #

    def _render_command(self, work_package: WorkPackage) -> str:
        """Build a deterministic shell command from the Work Package (INV-09: WP, not a Goal)."""
        return (
            f"nexus-run --package {work_package.identifier} --objective {work_package.objective!r}"
        )

    def _artifact_identifier(self, raw: RawShellEvent, work_package: WorkPackage) -> str:
        path = raw.data.get("path")
        suffix = path if isinstance(path, str) else (raw.name or "artifact")
        return f"{work_package.identifier}-{suffix}"
