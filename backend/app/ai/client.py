"""Provider interface for the language model, plus the Meta Model API client.

The rest of the app only knows `ModelClient`. Tests use a fake one; production
uses `HttpModelClient`. The API key is read from settings and is never logged
or included in any error text.
"""

import time
from typing import Any, Protocol

import httpx

from app.config import Settings


RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class ModelUnavailable(Exception):
    """The model could not be reached or gave an unusable HTTP answer."""


class ModelClient(Protocol):
    name: str

    def chat(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Return the assistant message (OpenAI chat format)."""
        ...


class HttpModelClient:
    def __init__(self, settings: Settings) -> None:
        self.name = settings.model_name
        self._url = settings.model_base_url.rstrip("/") + "/chat/completions"
        self._key = settings.model_api_key
        self._timeout = settings.model_timeout_s

    def chat(self, *, messages, tools=None, response_format=None):
        body: dict[str, Any] = {
            "model": self.name,
            "messages": messages,
            "reasoning_effort": "low",  # short, grounded explanations; keeps cost down
        }
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"
        if response_format:
            body["response_format"] = response_format
        # One quick retry for short-lived trouble (rate limit, server error, dropped connection).
        # A read timeout is not retried: that request already waited the full time.
        for attempt in (1, 2):
            try:
                r = httpx.post(
                    self._url,
                    json=body,
                    headers={"Authorization": f"Bearer {self._key}"},
                    timeout=self._timeout,
                )
                r.raise_for_status()
                return r.json()["choices"][0]["message"]
            except httpx.HTTPStatusError as e:
                if attempt == 1 and e.response.status_code in RETRYABLE_STATUS:
                    time.sleep(1.5)
                    continue
                raise ModelUnavailable(f"model API returned HTTP {e.response.status_code}") from None
            except httpx.ConnectError:
                if attempt == 1:
                    time.sleep(1.5)
                    continue
                raise ModelUnavailable("model API unreachable") from None
            except (httpx.HTTPError, KeyError, IndexError, ValueError):
                raise ModelUnavailable("model API unreachable or malformed answer") from None
        raise ModelUnavailable("model API unreachable")


def build_client(settings: Settings) -> ModelClient | None:
    return HttpModelClient(settings) if settings.model_api_key else None
