"""Unit tests for nexus_runtime_shell.invoker — the wire boundary + subprocess runner.

The deterministic stub is exercised directly; the real-subprocess invoker is exercised with a
monkeypatched ``subprocess.Popen`` (no real shell), so every branch — normal stream, exit
code, mid-stream cancellation, and the kill-on-teardown finally — is covered deterministically.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from nexus_execution.adapter import ExecutionControl
from nexus_runtime_shell import invoker as invoker_module
from nexus_runtime_shell.invoker import (
    RawShellEvent,
    RawShellKind,
    StubShellInvoker,
    SubprocessShellInvoker,
)


def _collect(
    invoker: StubShellInvoker, *, control: ExecutionControl | None = None
) -> list[RawShellEvent]:
    return list(
        invoker.invoke(command="run", working_dir=".", control=control or ExecutionControl())
    )


# StubShellInvoker ---------------------------------------------------------- #


def test_stub_is_deterministic() -> None:
    assert _collect(StubShellInvoker()) == _collect(StubShellInvoker())


def test_stub_ends_with_zero_exit() -> None:
    events = _collect(StubShellInvoker())
    assert events[-1].kind is RawShellKind.EXIT
    assert events[-1].exit_status == 0


def test_stub_emits_stdout_and_artifact() -> None:
    kinds = [e.kind for e in _collect(StubShellInvoker())]
    assert RawShellKind.STDOUT in kinds
    assert RawShellKind.ARTIFACT in kinds


def test_stub_fail_mode_emits_stderr_and_nonzero_exit() -> None:
    events = _collect(StubShellInvoker(fail=True))
    assert any(e.kind is RawShellKind.STDERR for e in events)
    assert events[-1].kind is RawShellKind.EXIT
    assert events[-1].exit_status == 127


def test_stub_hang_mode_stops_on_cancel() -> None:
    invoker = StubShellInvoker(hang=True)
    control = ExecutionControl()
    collected: list[RawShellEvent] = []
    for event in invoker.invoke(command="c", working_dir=".", control=control):
        collected.append(event)
        if len(collected) >= 5:
            control.cancel()
        if len(collected) >= 12:  # safety net
            break
    assert len(collected) < 12


# SubprocessShellInvoker with a monkeypatched Popen ------------------------- #


class _FakePopen:
    def __init__(
        self, lines: list[str], *, returncode: int = 0, stay_running: bool = False
    ) -> None:
        self.stdout: Iterator[str] = iter(lines)
        self.returncode = returncode
        self._stay_running = stay_running
        self.terminated = False
        self.killed = False
        self._waited = False

    def terminate(self) -> None:
        self.terminated = True

    def wait(self) -> int:
        self._waited = True
        return self.returncode

    def poll(self) -> int | None:
        if self._stay_running and not self._waited:
            return None
        return self.returncode

    def kill(self) -> None:
        self.killed = True


def _patch_popen(monkeypatch: pytest.MonkeyPatch, popen: _FakePopen) -> None:
    def factory(*_args: Any, **_kwargs: Any) -> _FakePopen:
        return popen

    monkeypatch.setattr(invoker_module.subprocess, "Popen", factory)


def test_subprocess_streams_and_exits(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_popen(monkeypatch, _FakePopen(["line one\n", "\n", "line two\n"], returncode=0))
    events = list(
        SubprocessShellInvoker().invoke(command="ls", working_dir="", control=ExecutionControl())
    )
    stdout = [e for e in events if e.kind is RawShellKind.STDOUT]
    assert [e.text for e in stdout] == ["line one", "line two"]  # blank line skipped
    assert events[-1].kind is RawShellKind.EXIT
    assert events[-1].exit_status == 0


def test_subprocess_reports_nonzero_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_popen(monkeypatch, _FakePopen(["boom\n"], returncode=3))
    events = list(
        SubprocessShellInvoker().invoke(command="x", working_dir=".", control=ExecutionControl())
    )
    assert events[-1].kind is RawShellKind.EXIT
    assert events[-1].exit_status == 3


def test_subprocess_cancels_and_kills(monkeypatch: pytest.MonkeyPatch) -> None:
    popen = _FakePopen(["a\n", "b\n"], stay_running=True)
    _patch_popen(monkeypatch, popen)
    control = ExecutionControl()
    control.cancel()
    events = list(SubprocessShellInvoker().invoke(command="x", working_dir=".", control=control))
    assert events == []
    assert popen.terminated is True
    assert popen.killed is True  # finally: poll() is None → kill
