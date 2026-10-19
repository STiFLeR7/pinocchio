"""Unit tests for nexus_runtime_shell.adapter — descriptor, configure, normalization, cleanup.

Verifies the Shell adapter satisfies the generic RuntimeAdapter contract and normalizes every
raw shell event (stdout/stderr/artifact/exit) into a runtime-independent signal, maps a
non-zero exit onto the doc-11 model, and renders a Work-Package command.
"""

from __future__ import annotations

from collections.abc import Iterator

from nexus_core.contracts.base import Reference
from nexus_core.registries.interfaces import HarnessCategory
from nexus_execution.adapter import AdapterConfig, ExecutionControl, RuntimeAdapter
from nexus_execution.signals import (
    ArtifactSignal,
    OutputSignal,
    StreamChannel,
    TerminalOutcome,
    TerminalSignal,
)
from nexus_runtime_shell import ShellRuntimeAdapter, StubShellInvoker
from nexus_runtime_shell.invoker import RawShellEvent, RawShellKind, ShellInvoker
from tests.unit.nexus_runtime.helpers import work_package


def _adapter(**kwargs: object) -> ShellRuntimeAdapter:
    return ShellRuntimeAdapter(invoker=StubShellInvoker(**kwargs))  # type: ignore[arg-type]


def _drive(adapter: ShellRuntimeAdapter) -> list[object]:
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
    assert descriptor.identity == "shell"
    caps = [c.identifier for c in descriptor.advertised_capabilities]
    assert "command_execution" in caps
    assert "code_generation" in caps  # cross-runtime compatible with model runtimes
    assert "file_write" in caps


def test_adapter_satisfies_protocol() -> None:
    assert isinstance(_adapter(), RuntimeAdapter)


# B — Configure ------------------------------------------------------------- #


def test_configure_echoes_secret_free() -> None:
    echo = _adapter().configure(
        AdapterConfig(working_dir="/w", env_keys=("PATH",), isolation_profile="process")
    )
    assert echo.working_dir == "/w"
    assert echo.env_keys == ("PATH",)
    assert echo.runtime_identity == "shell"


# C/D/E/F/H — Execute + normalization --------------------------------------- #


def test_execute_streams_stdout_then_completes() -> None:
    signals = _drive(_adapter())
    assert isinstance(signals[0], OutputSignal)
    assert signals[0].channel is StreamChannel.STDOUT
    assert isinstance(signals[-1], TerminalSignal)
    assert signals[-1].outcome is TerminalOutcome.COMPLETED
    assert signals[-1].exit_status == 0


def test_execute_emits_no_progress_signals() -> None:
    # A shell has no progress vocabulary — only output/artifact/terminal signals.
    from nexus_execution.signals import ProgressSignal

    assert not [s for s in _drive(_adapter()) if isinstance(s, ProgressSignal)]


def test_execute_normalizes_artifact_by_reference() -> None:
    artifacts = [s for s in _drive(_adapter()) if isinstance(s, ArtifactSignal)]
    assert artifacts
    assert artifacts[0].artifact_ref.identifier == "wp-1-output.txt"


def test_execute_fail_maps_stderr_and_failed_terminal() -> None:
    signals = _drive(_adapter(fail=True))
    stderr = [
        s for s in signals if isinstance(s, OutputSignal) and s.channel is StreamChannel.STDERR
    ]
    assert stderr
    terminal = signals[-1]
    assert isinstance(terminal, TerminalSignal)
    assert terminal.outcome is TerminalOutcome.FAILED
    assert terminal.error_class == "provider-failure"
    assert terminal.exit_status == 127


def test_cleanup_is_ok() -> None:
    assert _adapter().cleanup().ok is True


# Command rendering (INV-09) ------------------------------------------------ #


def test_command_includes_package_and_objective() -> None:
    adapter = _adapter()
    wp = work_package("wp-cmd")
    command = adapter._render_command(wp)
    assert "wp-cmd" in command
    assert "accomplish wp-cmd" in command


# Stream-ends-without-exit branch ------------------------------------------- #


class _OutputOnlyInvoker:
    """Yields stdout but never an EXIT — the adapter must synthesize a completion."""

    def invoke(
        self, *, command: str, working_dir: str, control: ExecutionControl
    ) -> Iterator[RawShellEvent]:
        yield RawShellEvent(RawShellKind.STDOUT, text="hello")


def test_stream_without_exit_synthesizes_completion() -> None:
    adapter = ShellRuntimeAdapter(invoker=_OutputOnlyInvoker())
    terminal = _drive(adapter)[-1]
    assert isinstance(terminal, TerminalSignal)
    assert terminal.outcome is TerminalOutcome.COMPLETED
    assert terminal.detail == "stream ended"


def test_output_only_invoker_satisfies_protocol() -> None:
    assert isinstance(_OutputOnlyInvoker(), ShellInvoker)


def test_artifact_identifier_falls_back_to_name() -> None:
    adapter = _adapter()
    raw = RawShellEvent(RawShellKind.ARTIFACT, name="report", data={})
    assert adapter._artifact_identifier(raw, work_package("wp-2")) == "wp-2-report"


def test_default_invoker_is_the_stub() -> None:
    assert _drive(ShellRuntimeAdapter())[-1].outcome is TerminalOutcome.COMPLETED  # type: ignore[union-attr]
