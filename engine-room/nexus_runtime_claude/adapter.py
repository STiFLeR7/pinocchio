"""The Claude Runtime Adapter — all Claude-specific behavior, and nothing generic.

This is the *only* place in the vertical slice where the word "Claude" drives behavior
(doc 03 §1). It implements the generic :class:`~nexus_execution.adapter.RuntimeAdapter`
protocol for Claude Code, satisfying the nine concerns:

* **A Advertise** — a ``RUNTIME`` descriptor advertising abstract capabilities (``05``);
* **B Configure** — echo RM's rendered config secret-free (``17`` §3);
* **C/D/E/F/H Execute** — render the Work Package into a prompt, drive the injected
  :class:`~nexus_runtime_claude.invoker.ClaudeInvoker`, and **semantically normalize**
  (doc 22 §3) each raw Claude event into a runtime-independent signal;
* **I Clean up** — release the (stub or subprocess) session.

It decides nothing (doc 03 §6): it does not select itself, choose when to cancel, or grade
output. It reports honest facts — including *unknown* progress (doc 12) — and maps a Claude
error onto the doc-11 model via a FAILED terminal signal. RM core and the Execution Engine
never import this module.
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
    ProgressSignal,
    RuntimeSignal,
    StreamChannel,
    TerminalOutcome,
    TerminalSignal,
)
from nexus_runtime_claude.invoker import (
    ClaudeInvoker,
    RawClaudeEvent,
    RawClaudeKind,
    StubClaudeInvoker,
)

CLAUDE_RUNTIME_IDENTITY = "claude-code"
CLAUDE_CAPABILITIES = ("code_generation", "file_write")
_ARTIFACT_TARGET_TYPE = "artifact"


class ClaudeRuntimeAdapter:
    """Drives Claude Code behind the generic adapter contract (doc 03; all provider logic here)."""

    def __init__(
        self,
        *,
        invoker: ClaudeInvoker | None = None,
        identity: str = CLAUDE_RUNTIME_IDENTITY,
        version: str = "1",
        working_dir: str = ".",
    ) -> None:
        self._invoker = invoker or StubClaudeInvoker()
        self._identity = identity
        self._version = version
        # RM's ``configure`` may later override this by reference (doc 17 §3); construction-time
        # ``working_dir`` lets a caller point the adapter at a real workspace when the Execution
        # Engine drives the adapter directly (it performs; it does not re-configure).
        self._working_dir = working_dir
        self._configured = False

    # -- A: Advertise -------------------------------------------------------- #

    def descriptor(self) -> HarnessDescriptor:
        """Advertise a ``RUNTIME`` descriptor with abstract, provider-independent capabilities."""
        return HarnessDescriptor(
            identity=self._identity,
            category=HarnessCategory.RUNTIME,
            version=self._version,
            advertised_capabilities=tuple(
                Reference(target_type="capability", identifier=c) for c in CLAUDE_CAPABILITIES
            ),
            availability=ResourceAvailability.AVAILABLE,
            health=ResourceAvailability.AVAILABLE,
            metadata={"provider": "claude-code"},
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
        """Render the Work Package into a prompt, drive Claude, normalize each event to a signal."""
        prompt = self._render_prompt(work_package)
        yield ProgressSignal(phase="starting", fraction=None, milestone="claude session opened")
        for raw in self._invoker.invoke(
            prompt=prompt, working_dir=self._working_dir, control=control
        ):
            yield self._normalize(raw, work_package)
            if raw.kind in (RawClaudeKind.RESULT, RawClaudeKind.ERROR):
                return
        # Stream ended without an explicit result — report an honest completion.
        yield TerminalSignal(TerminalOutcome.COMPLETED, exit_status=0, detail="stream ended")

    def _normalize(self, raw: RawClaudeEvent, work_package: WorkPackage) -> RuntimeSignal:
        """Semantic normalization (doc 22 §3): raw Claude event → runtime-independent signal."""
        if raw.kind is RawClaudeKind.TEXT:
            return OutputSignal(channel=StreamChannel.STDOUT, text=raw.text + "\n")
        if raw.kind is RawClaudeKind.TOOL_USE:
            # A tool use is a milestone with no reliable fraction — honest 'unknown' (doc 12).
            return ProgressSignal(phase="tool_use", fraction=None, milestone=raw.name or raw.text)
        if raw.kind is RawClaudeKind.ARTIFACT:
            identifier = self._artifact_identifier(raw, work_package)
            return ArtifactSignal(
                artifact_ref=Reference(target_type=_ARTIFACT_TARGET_TYPE, identifier=identifier),
                kind=raw.name or "file",
            )
        if raw.kind is RawClaudeKind.RESULT:
            return TerminalSignal(TerminalOutcome.COMPLETED, exit_status=raw.exit_status or 0)
        # RawClaudeKind.ERROR — map onto the doc-11 error model (provider failure).
        fault = ProviderError(raw.text or "claude reported an error")
        return TerminalSignal(
            TerminalOutcome.FAILED,
            exit_status=raw.exit_status,
            detail=fault.detail,
            error_class=fault.error_class,
        )

    # -- I: Clean up --------------------------------------------------------- #

    def cleanup(self) -> TeardownReport:
        """Release the Claude session; the stub holds no OS resource, so cleanup is trivial."""
        self._configured = False
        return TeardownReport(ok=True)

    # -- helpers ------------------------------------------------------------- #

    def _render_prompt(self, work_package: WorkPackage) -> str:
        """Build a deterministic Claude prompt from the Work Package (INV-09: WP, not a Goal)."""
        skills = ", ".join(s.identifier for s in work_package.skills) or "none"
        return (
            f"Work Package: {work_package.identifier}\n"
            f"Objective: {work_package.objective}\n"
            f"Priority: {work_package.priority.value}\n"
            f"Skills: {skills}\n"
        )

    def _artifact_identifier(self, raw: RawClaudeEvent, work_package: WorkPackage) -> str:
        path = raw.data.get("path")
        suffix = path if isinstance(path, str) else (raw.name or "artifact")
        return f"{work_package.identifier}-{suffix}"
