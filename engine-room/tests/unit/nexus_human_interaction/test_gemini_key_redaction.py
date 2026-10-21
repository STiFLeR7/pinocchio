from __future__ import annotations

import httpx

from nexus_execution.adapter import ExecutionControl
from nexus_runtime_llm.invoker import GeminiInvoker, RawLLMKind


def test_gemini_transport_error_does_not_put_key_in_url_or_error(monkeypatch) -> None:
    key = "test-secret-key"
    observed: dict[str, object] = {}

    class OfflineClient:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def __enter__(self) -> OfflineClient:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def post(self, url: str, *, headers: dict[str, str], json: dict[str, object]) -> None:
            observed["url"] = str(url)
            observed["headers"] = headers
            request = httpx.Request("POST", url, headers=headers)
            raise httpx.ConnectError(f"connection failed for {request.url}", request=request)

    monkeypatch.setattr("nexus_runtime_llm.invoker.httpx.Client", OfflineClient)
    event = next(
        GeminiInvoker(api_key=key, model="gemini-test").invoke(
            prompt="hello", working_dir=".", control=ExecutionControl()
        )
    )

    assert event.kind is RawLLMKind.ERROR
    assert key not in str(observed["url"])
    assert observed["headers"] == {"x-goog-api-key": key}
    assert key not in event.text
