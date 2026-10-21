"""``nexus_runtime_shell`` — the Shell Runtime Adapter (Capability Program 2, Milestone 3).

The single place shell-specific behavior lives (doc 03 §1/§3). It implements the generic
:class:`~nexus_execution.adapter.RuntimeAdapter` protocol for a local shell: advertise
capabilities, configure (secret-free), execute (render the Work Package into a command, drive
an injected shell invoker, and semantically normalize each raw shell event — stdout/stderr to
output, produced files to artifacts, exit code to a terminal), and clean up. A non-zero exit
maps onto the doc-11 error model. It contains **no business logic**.

Two invokers back the adapter: a deterministic :class:`StubShellInvoker` for reproducible
CI/E2E runs, and a :class:`SubprocessShellInvoker` that runs a real command for an opt-in
smoke test. Dependency direction: ``nexus_runtime_shell → {nexus_execution, nexus_core}`` —
identical to the Claude/Gemini adapters, proving the Runtime abstraction is provider-agnostic.
"""

from __future__ import annotations

from nexus_runtime_shell.adapter import (
    SHELL_CAPABILITIES,
    SHELL_RUNTIME_IDENTITY,
    ShellRuntimeAdapter,
)
from nexus_runtime_shell.invoker import (
    RawShellEvent,
    RawShellKind,
    ShellInvoker,
    StubShellInvoker,
    SubprocessShellInvoker,
)

__version__ = "2.5.0"

__all__ = [
    "SHELL_CAPABILITIES",
    "SHELL_RUNTIME_IDENTITY",
    "RawShellEvent",
    "RawShellKind",
    "ShellInvoker",
    "ShellRuntimeAdapter",
    "StubShellInvoker",
    "SubprocessShellInvoker",
]
