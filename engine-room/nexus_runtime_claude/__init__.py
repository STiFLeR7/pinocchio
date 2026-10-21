"""``nexus_runtime_claude`` — the Claude Runtime Adapter (Milestone 2 of the slice).

The single place provider-specific ("Claude") behavior lives (doc 03 §1/§3). It implements
the generic :class:`~nexus_execution.adapter.RuntimeAdapter` protocol for Claude Code:
advertise capabilities, configure (secret-free), execute (render the Work Package into a
prompt, drive an injected Claude invoker, and semantically normalize each raw Claude event
into a runtime-independent signal), and clean up. It maps Claude errors onto the doc-11
error model. RM core and the Execution Engine import nothing from here.

Two invokers back the adapter (doc, Decision 2): a deterministic :class:`StubClaudeInvoker`
for reproducible CI/E2E runs, and a :class:`ClaudeCliInvoker` that shells to the real
``claude`` CLI for an opt-in smoke test. Dependency direction:
``nexus_runtime_claude → {nexus_execution, nexus_core}``.
"""

from __future__ import annotations

from nexus_runtime_claude.adapter import (
    CLAUDE_CAPABILITIES,
    CLAUDE_RUNTIME_IDENTITY,
    ClaudeRuntimeAdapter,
)
from nexus_runtime_claude.invoker import (
    ClaudeCliInvoker,
    ClaudeInvoker,
    RawClaudeEvent,
    RawClaudeKind,
    StubClaudeInvoker,
)

__version__ = "2.5.0"

__all__ = [
    "CLAUDE_CAPABILITIES",
    "CLAUDE_RUNTIME_IDENTITY",
    "ClaudeCliInvoker",
    "ClaudeInvoker",
    "ClaudeRuntimeAdapter",
    "RawClaudeEvent",
    "RawClaudeKind",
    "StubClaudeInvoker",
]
