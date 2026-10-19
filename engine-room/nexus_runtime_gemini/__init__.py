"""``nexus_runtime_gemini`` — the Gemini Runtime Adapter (Capability Program 2, Milestone 2).

The single place provider-specific ("Gemini") behavior lives (doc 03 §1/§3). It implements
the generic :class:`~nexus_execution.adapter.RuntimeAdapter` protocol for Google's Gemini
CLI: advertise capabilities, configure (secret-free), execute (render the Work Package into
a prompt, drive an injected Gemini invoker, and semantically normalize each raw Gemini event
into a runtime-independent signal), and clean up. It maps Gemini errors onto the doc-11 error
model. RM core and the Execution Engine import nothing from here.

Two invokers back the adapter: a deterministic :class:`StubGeminiInvoker` for reproducible
CI/E2E runs, and a :class:`GeminiCliInvoker` that shells to the real ``gemini`` CLI for an
opt-in smoke test. Dependency direction: ``nexus_runtime_gemini → {nexus_execution,
nexus_core}`` — identical to the Claude adapter, proving the abstraction is provider-agnostic.
"""

from __future__ import annotations

from nexus_runtime_gemini.adapter import (
    GEMINI_CAPABILITIES,
    GEMINI_RUNTIME_IDENTITY,
    GeminiRuntimeAdapter,
)
from nexus_runtime_gemini.invoker import (
    GeminiCliInvoker,
    GeminiInvoker,
    RawGeminiEvent,
    RawGeminiKind,
    StubGeminiInvoker,
)

__version__ = "2.5.0"

__all__ = [
    "GEMINI_CAPABILITIES",
    "GEMINI_RUNTIME_IDENTITY",
    "GeminiCliInvoker",
    "GeminiInvoker",
    "GeminiRuntimeAdapter",
    "RawGeminiEvent",
    "RawGeminiKind",
    "StubGeminiInvoker",
]
