"""The LLM Runtime Adapter — the first *real* (non-CLI-shelling) provider-agnostic runtime.

Implements the generic :class:`~nexus_execution.adapter.RuntimeAdapter` protocol (doc 03's nine
concerns), exactly as ``nexus_runtime_claude``/``nexus_runtime_gemini``/``nexus_runtime_shell``
already do. It names no provider: which real API answers a Work Package is entirely a property of
the injected :class:`~nexus_runtime_llm.invoker.LLMInvoker` (see
:mod:`nexus_runtime_llm.config` for how a provider is chosen from configuration) — Anthropic,
OpenAI, OpenRouter, and Gemini are interchangeable through that one seam, never through a branch
in this module (doc 03 §1 litmus, applied one level below "which runtime" to "which provider").

It decides nothing (doc 03 §6): it does not select itself, choose when to cancel, or grade its own
output — it reports honest facts and maps a wire/provider fault onto the doc-11 error model via a
FAILED terminal signal. RM core and the Execution Engine never import this module.

Scope, disclosed rather than silently assumed: this adapter answers in text and performs no tool
calls (an agentic tool loop is out of scope for this vertical slice). Its complete answer *is*
still durably retrievable, though: the runtime-signal contract already has a mechanism for exactly
this (``ArtifactSignal`` — "an Evidence Candidate referenced by id, never by content", doc 13), the
same one ``nexus_runtime_claude`` uses for a written file. This adapter writes its accumulated
answer text to one file under the configured working directory and references it the same way —
no new mechanism, the existing one applied to a text answer instead of a source file. Without this,
the answer would exist only as transient process output: the durable ``runtime.output`` event
records a chunk's *length*, never its content (INV-27), so nothing downstream could read it back
after the run.
"""

from __future__ import annotations

import os
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
from nexus_execution.errors import ProviderError, TransportError
from nexus_execution.signals import (
    ArtifactSignal,
    OutputSignal,
    ProgressSignal,
    RuntimeSignal,
    StreamChannel,
    TerminalOutcome,
    TerminalSignal,
)
from nexus_runtime_llm.invoker import LLMInvoker, RawLLMEvent, RawLLMKind, StubLLMInvoker

LLM_RUNTIME_IDENTITY = "nexus-llm"
LLM_CAPABILITIES = ("code_generation", "text_generation")
_ARTIFACT_TARGET_TYPE = "artifact"
_RESPONSE_SUFFIX = "response.md"


class LLMRuntimeAdapter:
    """Drives a real (or stub) LLM provider behind the generic adapter contract (doc 03).

    All provider-specific behavior lives in the injected :class:`LLMInvoker`; this class contains
    none. Constructed with no invoker, it defaults to :class:`StubLLMInvoker` — deterministic,
    network-free — matching every other adapter's production-safe default.
    """

    def __init__(
        self,
        *,
        invoker: LLMInvoker | None = None,
        identity: str = LLM_RUNTIME_IDENTITY,
        version: str = "1",
        working_dir: str = ".",
    ) -> None:
        self._invoker = invoker or StubLLMInvoker()
        self._identity = identity
        self._version = version
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
                Reference(target_type="capability", identifier=c) for c in LLM_CAPABILITIES
            ),
            availability=ResourceAvailability.AVAILABLE,
            health=ResourceAvailability.AVAILABLE,
            metadata={"provider": "configurable"},
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
        """Render the Work Package into a prompt, drive the LLM, normalize each event to a signal."""
        prompt = self._render_prompt(work_package)
        yield ProgressSignal(phase="starting", fraction=None, milestone="llm request opened")
        answer_parts: list[str] = []
        for raw in self._invoker.invoke(
            prompt=prompt, working_dir=self._working_dir, control=control
        ):
            if raw.kind is RawLLMKind.TEXT:
                answer_parts.append(raw.text)
                yield self._normalize(raw)
                continue
            # RESULT/ERROR normalize to a TerminalSignal — the engine stops consuming the moment
            # it sees one (`ExecutionEngine._consume`), so the artifact must be yielded *first*.
            if raw.kind is RawLLMKind.RESULT and answer_parts:
                yield self._write_answer_artifact(work_package, "".join(answer_parts))
            yield self._normalize(raw)
            return
        # Stream ended without an explicit result — report an honest completion.
        if answer_parts:
            yield self._write_answer_artifact(work_package, "".join(answer_parts))
        yield TerminalSignal(TerminalOutcome.COMPLETED, exit_status=0, detail="stream ended")

    def _normalize(self, raw: RawLLMEvent) -> RuntimeSignal:
        """Semantic normalization (doc 22 §3): raw LLM event → runtime-independent signal."""
        if raw.kind is RawLLMKind.TEXT:
            return OutputSignal(channel=StreamChannel.STDOUT, text=raw.text)
        if raw.kind is RawLLMKind.RESULT:
            return TerminalSignal(TerminalOutcome.COMPLETED, exit_status=raw.exit_status or 0)
        # RawLLMKind.ERROR — map onto the doc-11 error model, distinguishing transport from
        # provider faults so the failure class is honest rather than collapsed into one.
        fault: ProviderError | TransportError
        fault = TransportError(raw.text) if raw.is_transport_fault else ProviderError(raw.text)
        return TerminalSignal(
            TerminalOutcome.FAILED,
            exit_status=None,
            detail=fault.detail,
            error_class=fault.error_class,
        )

    # -- I: Clean up --------------------------------------------------------- #

    def cleanup(self) -> TeardownReport:
        """Release the LLM session; a plain HTTP request holds no OS resource, so this is trivial."""
        self._configured = False
        return TeardownReport(ok=True)

    # -- helpers ------------------------------------------------------------- #

    def _write_answer_artifact(self, work_package: WorkPackage, text: str) -> ArtifactSignal:
        """Write the accumulated answer to one file under the working dir; reference it by id.

        Mirrors ``nexus_runtime_claude``'s own artifact identifier shape
        (``f"{work_package.identifier}-{suffix}"``) — the same referenced-not-embedded discipline
        (INV-27), applied to a text answer instead of a source file.
        """
        identifier = f"{work_package.identifier}-{_RESPONSE_SUFFIX}"
        os.makedirs(self._working_dir, exist_ok=True)
        path = os.path.join(self._working_dir, identifier)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return ArtifactSignal(
            artifact_ref=Reference(target_type=_ARTIFACT_TARGET_TYPE, identifier=identifier),
            kind="text_response",
        )

    def _render_prompt(self, work_package: WorkPackage) -> str:
        """Build a deterministic prompt from the Work Package (INV-09: WP, not a Goal)."""
        skills = ", ".join(s.identifier for s in work_package.skills) or "none"
        return (
            f"Work Package: {work_package.identifier}\n"
            f"Objective: {work_package.objective}\n"
            f"Priority: {work_package.priority.value}\n"
            f"Skills: {skills}\n"
        )
