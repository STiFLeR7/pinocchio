"""OpenRouter LLM gateway integration client.

Handles connection to the OpenRouter completions API, error catching,
and sequential model fallbacks.
"""

from __future__ import annotations

from typing import Any

import httpx
import structlog

from nexus.config import get_settings
from nexus.core.exceptions import ModelRouterError

logger = structlog.get_logger("nexus.intelligence.openrouter")


class OpenRouterClient:
    """Gateway client to generate completions via OpenRouter with fallbacks."""

    def __init__(self, settings: Any = None) -> None:
        """Initialize settings and endpoints config."""
        self.settings = settings or get_settings()

    def _build_providers(self) -> list[tuple[str, str, str, list[str]]]:
        """Build the ordered (name, base_url, api_key, models) provider fallback chain.

        Uses every available OpenAI-compatible provider key so LLM operation is resilient to any
        single provider's rate-limits/credits: Groq → Zenmux → OpenRouter. Keys are read from the
        environment (the deployed .env); never logged.
        """
        import os

        providers: list[tuple[str, str, str, list[str]]] = []
        groq_key = os.getenv("GROQ_API_KEY")
        if groq_key:
            providers.append((
                "groq", "https://api.groq.com/openai/v1", groq_key,
                ["llama-3.3-70b-versatile", "meta-llama/llama-4-scout-17b-16e-instruct"],
            ))
        zenmux_key = os.getenv("ZENMUX_API")
        if zenmux_key:
            providers.append((
                "zenmux", "https://zenmux.ai/api/v1", zenmux_key, ["z-ai/glm-5.2"],
            ))
        or_key = self.settings.openrouter.api_key
        if or_key:
            providers.append((
                "openrouter", self.settings.openrouter.base_url, or_key,
                [self.settings.openrouter.primary_model, *self.settings.openrouter.fallback_models],
            ))
        return providers

    async def complete(
        self,
        prompt: str,
        system_prompt: str | None = None,
        history: list[dict[str, str]] | None = None,
    ) -> str:
        """Post a completion across the multi-provider fallback chain (first success wins).

        ``history`` is an optional ordered list of prior ``{"role": "user"|"assistant",
        "content": ...}`` turns inserted between the system prompt and the current ``prompt`` so
        multi-turn chat keeps context.
        """
        import time

        providers = self._build_providers()
        if not providers:
            raise ModelRouterError(
                "No LLM provider key configured (GROQ_API_KEY / ZENMUX_API / OPENROUTER_API_KEY)."
            )

        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": prompt})

        last_error: Exception | None = None
        async with httpx.AsyncClient(timeout=30.0) as client:
            for prov_name, base_url, api_key, models in providers:
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com/STiFLeR7/nexus",
                    "X-Title": "Nexus Control Plane",
                }
                for model in models:
                    if not model:
                        continue
                    logger.info("attempting_llm_completion", provider=prov_name, model=model)
                    payload = {"model": model, "messages": messages, "temperature": 0.2}
                    try:
                        start_time = time.perf_counter()
                        res = await client.post(
                            f"{base_url}/chat/completions", json=payload, headers=headers
                        )
                        if res.status_code != 200:
                            raise httpx.HTTPStatusError(
                                f"{prov_name} API error: Status {res.status_code}. "
                                f"Response: {res.text}",
                                request=res.request,
                                response=res,
                            )
                        data = res.json()
                        choices = data.get("choices", [])
                        if not choices:
                            raise ModelRouterError(f"{prov_name} response had no choices: {data}")
                        content = choices[0].get("message", {}).get("content", "")
                        duration = (time.perf_counter() - start_time) * 1000.0
                        from nexus.core.metrics import record_metric

                        record_metric("openrouter_latency_ms", duration)
                        logger.info(
                            "llm_completion_successful",
                            provider=prov_name,
                            model=model,
                            openrouter_latency_ms=round(duration, 2),
                        )
                        return str(content)
                    except Exception as e:
                        logger.warning(
                            "llm_completion_failed_falling_back",
                            provider=prov_name,
                            model=model,
                            error=str(e),
                        )
                        last_error = e

        raise ModelRouterError(
            f"All configured providers/models failed completion. Last error: {last_error!s}"
        )
