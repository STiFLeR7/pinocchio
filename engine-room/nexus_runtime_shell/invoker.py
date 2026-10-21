"""Shell invokers — the *wire* boundary that produces provider-shaped shell events.

The transport-shaped sub-layer (doc 22 §3, doc 23) for a local shell runtime: it carries an
already-decided command and returns raw, **provider-vocabulary** events (stdout/stderr lines,
produced files, an exit code). It performs no Nexus semantics — the
:class:`~nexus_runtime_shell.adapter.ShellRuntimeAdapter` turns these raw events into
runtime-independent signals (semantic normalization). Two invokers ship:

* :class:`StubShellInvoker` — deterministic, subprocess-free; the CI/E2E path so the event
  stream is reproducible without touching the host shell;
* :class:`SubprocessShellInvoker` — runs a real command via :mod:`subprocess`; the opt-in
  path. Cancellation terminates the process between lines (doc 09, graceful-then-forced),
  and a wall-clock timeout is enforced by the process wait bound.

A shell has no "progress" or "tool use" vocabulary — its raw events are exactly command
output streams, produced artifacts, and a terminal exit code (doc 08/doc 11).
"""

from __future__ import annotations

import subprocess
from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol, runtime_checkable

from nexus_execution.adapter import ExecutionControl


class RawShellKind(StrEnum):
    """The provider-vocabulary kind of a raw shell event (pre-normalization)."""

    STDOUT = "stdout"
    STDERR = "stderr"
    ARTIFACT = "artifact"
    EXIT = "exit"


@dataclass(frozen=True, slots=True)
class RawShellEvent:
    """One provider-shaped event from a shell invocation (still in shell vocabulary)."""

    kind: RawShellKind
    text: str = ""
    name: str | None = None
    exit_status: int | None = None
    data: dict[str, object] = field(default_factory=dict)


@runtime_checkable
class ShellInvoker(Protocol):
    """Produces the raw shell event stream for a rendered command (the wire)."""

    def invoke(
        self, *, command: str, working_dir: str, control: ExecutionControl
    ) -> Iterator[RawShellEvent]:
        """Yield provider-shaped events for ``command`` until a terminal exit."""
        ...


class StubShellInvoker:
    """A deterministic, subprocess-free shell stand-in for reproducible runs.

    The stream is a pure function of the rendered command — no clock, no randomness — so two
    runs of the same Work Package yield byte-identical event streams (and therefore identical
    ``runtime.*`` events under a fixed timestamp source). It models the *shape* of a real
    command run: a couple of stdout lines, one produced file, then a zero exit — or, in fail
    mode, a stderr diagnostic and a non-zero exit.
    """

    def __init__(self, *, fail: bool = False, hang: bool = False) -> None:
        self._fail = fail
        self._hang = hang

    def invoke(
        self, *, command: str, working_dir: str, control: ExecutionControl
    ) -> Iterator[RawShellEvent]:
        digest = str(len(command))
        yield RawShellEvent(RawShellKind.STDOUT, text=f"$ running command ({digest} chars)")
        yield RawShellEvent(RawShellKind.ARTIFACT, name="output.txt", data={"path": "output.txt"})
        yield RawShellEvent(RawShellKind.STDOUT, text="wrote output.txt")
        if self._hang:
            # A cooperative, unbounded stream — the engine's cancel/timeout must stop it.
            while not control.cancelled:
                yield RawShellEvent(RawShellKind.STDOUT, text="…")
        if self._fail:
            yield RawShellEvent(RawShellKind.STDERR, text="command not found: build")
            yield RawShellEvent(RawShellKind.EXIT, exit_status=127)
            return
        yield RawShellEvent(RawShellKind.EXIT, exit_status=0)


class SubprocessShellInvoker:
    """Runs a real command via :mod:`subprocess` (opt-in path).

    Streams stdout line by line, checking cancellation between lines (doc 09). On completion
    it surfaces the process exit code; a non-zero exit is a terminal EXIT the adapter maps to
    a doc-11 failure. Kept deliberately small: it is exercised only by an opt-in smoke test.
    """

    def __init__(self, *, shell_path: str = "/bin/sh") -> None:
        self._shell_path = shell_path

    def invoke(
        self, *, command: str, working_dir: str, control: ExecutionControl
    ) -> Iterator[RawShellEvent]:
        process = subprocess.Popen(
            [self._shell_path, "-c", command],
            cwd=working_dir or None,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        try:
            assert process.stdout is not None
            for line in process.stdout:
                if control.cancelled:
                    process.terminate()
                    return
                stripped = line.rstrip("\n")
                if stripped:
                    yield RawShellEvent(RawShellKind.STDOUT, text=stripped)
            process.wait()
            yield RawShellEvent(RawShellKind.EXIT, exit_status=process.returncode)
        finally:
            if process.poll() is None:
                process.kill()
