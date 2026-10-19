"""LLM provider configuration — the one seam that turns "which provider" into an invoker.

Provider choice is **configuration, not architecture** (the adapter in
``nexus_runtime_llm.adapter`` never names a provider): a caller reads :class:`LLMProviderConfig`
from the environment and hands the resulting invoker to
:class:`~nexus_runtime_llm.adapter.LLMRuntimeAdapter`. Swapping Anthropic for OpenAI, OpenRouter,
or Gemini is a config change, never a code change to the adapter, mirroring
``nexus_runtime_adapters.catalog``'s "add a factory, change nothing else" discipline one level
down (provider, not runtime).

Fails closed twice over: with no provider configured at all, the platform-wide default is the
deterministic, network-free :class:`~nexus_runtime_llm.invoker.StubLLMInvoker` (nothing calls a
real API by accident); with a provider explicitly requested but its credential missing, this
raises immediately at config-load time rather than failing confusingly mid-run.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

from nexus_runtime_llm.invoker import (
    AnthropicInvoker,
    GeminiInvoker,
    LLMInvoker,
    OpenAICompatibleInvoker,
    StubLLMInvoker,
)

_DEFAULT_MODELS = {
    "anthropic": "claude-3-5-haiku-latest",
    "openai": "gpt-4o-mini",
    "openrouter": "anthropic/claude-3.5-haiku",
    "gemini": "gemini-1.5-flash",
}
_OPENAI_BASE_URL = "https://api.openai.com/v1"
_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
_ENV_KEYS = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "gemini": "GEMINI_API_KEY",
}


class LLMConfigError(Exception):
    """A provider was explicitly requested but cannot be configured (e.g. missing API key)."""


@dataclass(frozen=True, slots=True)
class LLMProviderConfig:
    """The resolved, secret-free-to-log configuration for one LLM provider choice.

    ``api_key`` is held here only transiently to build an invoker; it is never placed on a
    ``Struct``/event payload anywhere downstream (the adapter/invoker never log it) — the durable
    event log only ever sees the *response text*, never the credential.
    """

    provider: str
    api_key: str | None
    model: str
    base_url: str | None = None
    max_tokens: int = 1024


def load_llm_provider_config(env: Mapping[str, str] | None = None) -> LLMProviderConfig:
    """Resolve provider config from the environment (``NEXUS_LLM_PROVIDER`` + per-provider keys).

    Defaults to ``"stub"`` (no network, deterministic) when ``NEXUS_LLM_PROVIDER`` is unset, so a
    fresh checkout never makes a real network call without explicit operator configuration.
    """
    source = env if env is not None else os.environ
    provider = source.get("NEXUS_LLM_PROVIDER", "stub").strip().lower()
    if provider == "stub":
        return LLMProviderConfig(provider="stub", api_key=None, model="stub")

    if provider not in _ENV_KEYS:
        raise LLMConfigError(
            f"unknown NEXUS_LLM_PROVIDER {provider!r}; expected one of "
            f"{sorted({'stub', *_ENV_KEYS})!r}"
        )
    api_key = source.get(_ENV_KEYS[provider])
    if not api_key:
        raise LLMConfigError(
            f"NEXUS_LLM_PROVIDER={provider!r} requires {_ENV_KEYS[provider]} to be set"
        )
    model = source.get("NEXUS_LLM_MODEL", _DEFAULT_MODELS[provider])
    max_tokens = int(source.get("NEXUS_LLM_MAX_TOKENS", "1024"))
    base_url = {"openai": _OPENAI_BASE_URL, "openrouter": _OPENROUTER_BASE_URL}.get(provider)
    return LLMProviderConfig(
        provider=provider, api_key=api_key, model=model, base_url=base_url, max_tokens=max_tokens
    )


def build_llm_invoker(config: LLMProviderConfig) -> LLMInvoker:
    """Build the concrete invoker for ``config.provider`` (the only place providers are named)."""
    if config.provider == "stub":
        return StubLLMInvoker()
    if config.provider == "anthropic":
        assert config.api_key is not None
        return AnthropicInvoker(
            api_key=config.api_key, model=config.model, max_tokens=config.max_tokens
        )
    if config.provider in ("openai", "openrouter"):
        assert config.api_key is not None and config.base_url is not None
        return OpenAICompatibleInvoker(
            api_key=config.api_key,
            model=config.model,
            base_url=config.base_url,
            max_tokens=config.max_tokens,
        )
    if config.provider == "gemini":
        assert config.api_key is not None
        return GeminiInvoker(api_key=config.api_key, model=config.model)
    raise LLMConfigError(f"no invoker wired for provider {config.provider!r}")
