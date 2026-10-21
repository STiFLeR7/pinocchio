"""Unit tests for nexus_runtime_gemini.adapter — descriptor, configure, normalization, cleanup.

Verifies the Gemini adapter satisfies the generic RuntimeAdapter contract and performs the
semantic normalization (raw Gemini event → runtime-independent signal) correctly for every
raw kind, maps a Gemini error onto the doc-11 model, and renders a Work-Package prompt.
"""

from __future__ import annotations

from collections.abc import Iterator

from nexus_core.contracts.base import Reference
from nexus_core.contracts.enums import Priority
from nexus_core.registries.interfaces import HarnessCategory
from nexus_execution.adapter import AdapterConfig, ExecutionControl, RuntimeAdapter
from nexus_execution.signals import (
    ArtifactSignal,
    OutputSignal,
    ProgressSignal,
    StreamChannel,
    TerminalOutcome,
    TerminalSignal,
)
from nexus_runtime_gemini import GeminiRuntimeAdapter, StubGeminiInvoker
from nexus_runtime_gemini.invoker import GeminiInvoker, RawGeminiEvent, RawGeminiKind
from tests.unit.nexus_runtime.helpers import work_package


def _adapter(**kwargs: object) -> GeminiRuntimeAdapter:
    return GeminiRuntimeAdapter(invoker=StubGeminiInvoker(**kwargs))  # type: ignore[arg-type]


def _drive(adapter: GeminiRuntimeAdapter) -> list[object]:
    return list(
        adapter.execute(
            session_ref=Reference(target_type="runtime_session", identifier="s"),
            work_package=work_package("wp-1"),
            control=ExecutionControl(),
        )
    )


# A — Advertise ------------------------------------------------------------- #


def test_descriptor_is_a_runtime_with_capabilities() -> None:
    descriptor = _adapter().descriptor()
    assert descriptor.category is HarnessCategory.RUNTIME
    assert descriptor.identity == "gemini-cli"
    caps = [c.identifier for c in descriptor.advertised_capabilities]
    assert "code_generation" in caps
    assert "file_write" in caps


def test_adapter_satisfies_protocol() -> None:
    assert isinstance(_adapter(), RuntimeAdapter)


# B — Configure ------------------------------------------------------------- #


def test_configure_echoes_secret_free() -> None:
    echo = _adapter().configure(
        AdapterConfig(
            working_dir="/work", env_keys=("GEMINI_API_KEY",), isolation_profile="process"
        )
    )
    assert echo.working_dir == "/work"
    assert echo.env_keys == ("GEMINI_API_KEY",)
    assert echo.runtime_identity == "gemini-cli"


# C/D/E/F/H — Execute + normalization --------------------------------------- #


def test_execute_opens_with_progress_then_completes() -> None:
    signals = _drive(_adapter())
    assert isinstance(signals[0], ProgressSignal)
    assert signals[0].phase == "starting"
    assert isinstance(signals[-1], TerminalSignal)
    assert signals[-1].outcome is TerminalOutcome.COMPLETED


def test_execute_normalizes_text_to_stdout_output() -> None:
    outputs = [s for s in _drive(_adapter()) if isinstance(s, OutputSignal)]
    assert outputs
    assert outputs[0].channel is StreamChannel.STDOUT
    assert outputs[0].text.endswith("\n")


def test_execute_normalizes_tool_use_to_unknown_progress() -> None:
    tool_progress = [
        s for s in _drive(_adapter()) if isinstance(s, ProgressSignal) and s.phase == "tool_use"
    ]
    assert tool_progress
    assert tool_progress[0].fraction is None


def test_execute_normalizes_artifact_by_reference() -> None:
    artifacts = [s for s in _drive(_adapter()) if isinstance(s, ArtifactSignal)]
    assert artifacts
    assert artifacts[0].artifact_ref.identifier == "wp-1-summary.md"


def test_execute_fail_maps_to_failed_terminal_with_doc11_class() -> None:
    signals = _drive(_adapter(fail=True))
    terminal = signals[-1]
    assert isinstance(terminal, TerminalSignal)
    assert terminal.outcome is TerminalOutcome.FAILED
    assert terminal.error_class == "provider-failure"


def test_cleanup_is_ok() -> None:
    assert _adapter().cleanup().ok is True


# Prompt rendering (INV-09: a Work Package, never a Goal) -------------------- #


def test_prompt_includes_objective_and_priority() -> None:
    adapter = _adapter()
    wp = work_package("wp-render", priority=Priority.HIGH)
    prompt = adapter._render_prompt(wp)
    assert "wp-render" in prompt
    assert "accomplish wp-render" in prompt
    assert Priority.HIGH.value in prompt


def test_prompt_lists_skills_when_present() -> None:
    adapter = _adapter()
    wp = work_package("wp-s", skills=(Reference(target_type="skill", identifier="skill-x"),))
    assert "skill-x" in adapter._render_prompt(wp)


# Stream-ends-without-result branch ----------------------------------------- #


class _TextOnlyInvoker:
    """Yields text but never a RESULT/ERROR — the adapter must synthesize a completion."""

    def invoke(
        self, *, prompt: str, working_dir: str, control: ExecutionControl
    ) -> Iterator[RawGeminiEvent]:
        yield RawGeminiEvent(RawGeminiKind.TEXT, text="just talking")


def test_stream_without_result_synthesizes_completion() -> None:
    adapter = GeminiRuntimeAdapter(invoker=_TextOnlyInvoker())
    terminal = _drive(adapter)[-1]
    assert isinstance(terminal, TerminalSignal)
    assert terminal.outcome is TerminalOutcome.COMPLETED
    assert terminal.detail == "stream ended"


def test_text_only_invoker_satisfies_protocol() -> None:
    assert isinstance(_TextOnlyInvoker(), GeminiInvoker)


def test_artifact_identifier_falls_back_to_name() -> None:
    adapter = _adapter()
    raw = RawGeminiEvent(RawGeminiKind.ARTIFACT, name="report", data={})
    assert adapter._artifact_identifier(raw, work_package("wp-2")) == "wp-2-report"


def test_default_invoker_is_the_stub() -> None:
    # Constructing without an invoker uses the deterministic stub (drives to completion).
    assert _drive(GeminiRuntimeAdapter())[-1].outcome is TerminalOutcome.COMPLETED  # type: ignore[union-attr]
