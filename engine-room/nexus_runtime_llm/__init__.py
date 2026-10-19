"""``nexus_runtime_llm`` — the first real, provider-agnostic LLM Runtime Adapter (P0).

Implements the generic :class:`~nexus_execution.adapter.RuntimeAdapter` protocol for a real LLM
provider: advertise capabilities, configure (secret-free), execute (render the Work Package into a
prompt, drive an injected :class:`~nexus_runtime_llm.invoker.LLMInvoker`, semantically normalize
each raw event into a runtime-independent signal), and clean up. Which provider answers is a
configuration choice (:mod:`nexus_runtime_llm.config`), never a branch in the adapter — Anthropic,
OpenAI, OpenRouter, and Gemini are interchangeable through it.

Dependency direction: ``nexus_runtime_llm -> {nexus_execution, nexus_core}`` (plus ``httpx``,
already a platform dependency — no new SDK dependency was added).
"""

from __future__ import annotations

from nexus_runtime_llm.adapter import LLM_CAPABILITIES, LLM_RUNTIME_IDENTITY, LLMRuntimeAdapter
from nexus_runtime_llm.config import (
    LLMConfigError,
    LLMProviderConfig,
    build_llm_invoker,
    load_llm_provider_config,
)
from nexus_runtime_llm.invoker import (
    AnthropicInvoker,
    GeminiInvoker,
    LLMInvoker,
    OpenAICompatibleInvoker,
    RawLLMEvent,
    RawLLMKind,
    StubLLMInvoker,
)

__version__ = "2.5.0"

__all__ = [
    "LLM_CAPABILITIES",
    "LLM_RUNTIME_IDENTITY",
    "AnthropicInvoker",
    "GeminiInvoker",
    "LLMConfigError",
    "LLMInvoker",
    "LLMProviderConfig",
    "LLMRuntimeAdapter",
    "OpenAICompatibleInvoker",
    "RawLLMEvent",
    "RawLLMKind",
    "StubLLMInvoker",
    "build_llm_invoker",
    "load_llm_provider_config",
]
