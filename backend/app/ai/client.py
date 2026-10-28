"""Provider interface for the language model, plus the Meta Model API client.

The rest of the app only knows `ModelClient`. Tests use a fake one; production
uses `HttpModelClient`. The API key is read from settings and is never logged
or included in any error text.
"""

from typing import Any, Protocol

import httpx

from app.config import Settings


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
            raise ModelUnavailable(f"model API returned HTTP {e.response.status_code}") from None
        except (httpx.HTTPError, KeyError, IndexError, ValueError):
            raise ModelUnavailable("model API unreachable or malformed answer") from None


def build_client(settings: Settings) -> ModelClient | None:
    return HttpModelClient(settings) if settings.model_api_key else None
