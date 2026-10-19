"""The default adapter catalog — the one wiring boundary that names concrete providers.

:mod:`nexus_runtime_adapters.registry` and :mod:`~nexus_runtime_adapters.selection` are
runtime-independent (they import no concrete adapter). *This* module is the composition seam
that assembles the shipped runtimes — Claude, Gemini, Shell — into an :class:`AdapterRegistry`.
Adding a new execution environment means adding one factory here (or registering into a
registry from anywhere else): no registry, selector, or engine changes (the Runtime
abstraction is provider-agnostic, the program's thesis).

Each factory maps a :class:`RuntimeInvocationProfile` onto the provider's deterministic stub
invoker, so a chosen runtime produces a reproducible event stream (and the failure/cancel
paths are reachable via the profile).
"""

from __future__ import annotations

from nexus_runtime_adapters.registry import (
    AdapterRegistration,
    AdapterRegistry,
    RuntimeInvocationProfile,
)
from nexus_runtime_claude import ClaudeRuntimeAdapter, StubClaudeInvoker
from nexus_runtime_claude.adapter import CLAUDE_RUNTIME_IDENTITY
from nexus_runtime_gemini import GeminiRuntimeAdapter, StubGeminiInvoker
from nexus_runtime_gemini.adapter import GEMINI_RUNTIME_IDENTITY
from nexus_runtime_shell import ShellRuntimeAdapter, StubShellInvoker
from nexus_runtime_shell.adapter import SHELL_RUNTIME_IDENTITY


def _claude(profile: RuntimeInvocationProfile) -> ClaudeRuntimeAdapter:
    return ClaudeRuntimeAdapter(invoker=StubClaudeInvoker(fail=profile.fail, hang=profile.hang))


def _gemini(profile: RuntimeInvocationProfile) -> GeminiRuntimeAdapter:
    return GeminiRuntimeAdapter(invoker=StubGeminiInvoker(fail=profile.fail, hang=profile.hang))


def _shell(profile: RuntimeInvocationProfile) -> ShellRuntimeAdapter:
    return ShellRuntimeAdapter(invoker=StubShellInvoker(fail=profile.fail, hang=profile.hang))


def build_default_adapter_registry() -> AdapterRegistry:
    """An :class:`AdapterRegistry` pre-loaded with the shipped Claude/Gemini/Shell adapters."""
    registry = AdapterRegistry()
    registry.register(
        AdapterRegistration(
            identity=CLAUDE_RUNTIME_IDENTITY,
            descriptor=ClaudeRuntimeAdapter().descriptor(),
            factory=_claude,
        )
    )
    registry.register(
        AdapterRegistration(
            identity=GEMINI_RUNTIME_IDENTITY,
            descriptor=GeminiRuntimeAdapter().descriptor(),
            factory=_gemini,
        )
    )
    registry.register(
        AdapterRegistration(
            identity=SHELL_RUNTIME_IDENTITY,
            descriptor=ShellRuntimeAdapter().descriptor(),
            factory=_shell,
        )
    )
    return registry
