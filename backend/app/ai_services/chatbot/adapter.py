"""Provider boundary for the assistant.

Adapters receive plain text only and have no database session or banking tools.
The default is deliberately a no-provider response.  A production provider
must be implemented behind this interface and must not be granted mutation
tools or transaction execution privileges.
"""

from __future__ import annotations

import json
from urllib.error import URLError
from urllib.request import Request, urlopen
from typing import Protocol

from app.config import get_settings

class AssistantAdapter(Protocol):
    def answer(self, prompt: str) -> str:
        """Return a response without performing any external side effect."""


class NoProviderAdapter:
    """Safe behavior when no approved model provider is configured."""

    def __init__(self, message: str | None = None) -> None:
        self.message = message or (
            "The AI provider is not configured. I can still provide account, "
            "transaction-history, loan, and general financial-education information."
        )

    def answer(self, prompt: str) -> str:
        return self.message


class ConfiguredProviderAdapter:
    """Safe response for an unsupported provider name."""

    def __init__(self, provider_name: str) -> None:
        self.provider_name = provider_name

    def answer(self, prompt: str) -> str:
        # Network/model integration is intentionally not implicit or enabled.
        return (
            f"The configured provider '{self.provider_name}' is not enabled in "
            "this deployment. Please use the supported read-only banking queries."
        )


SAFE_SYSTEM_PROMPT = (
    "You are a banking financial-education assistant. Answer only generic FAQ "
    "and financial-education questions. Do not request, infer, or handle "
    "customer data, account data, transaction data, loan data, credentials, "
    "or payments. Never provide tools, function calls, or instructions to "
    "execute financial transactions. State when professional advice is needed."
)


class OpenAICompatibleAdapter:
    """Opt-in JSON chat-completions adapter with no tool/function calling."""

    def __init__(
        self,
        api_url: str,
        api_key: str,
        model: str,
        timeout_seconds: float = 10.0,
    ) -> None:
        self.api_url = api_url
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = max(1.0, min(timeout_seconds, 30.0))

    def answer(self, prompt: str) -> str:
        body = json.dumps(
            {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": SAFE_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.2,
            }
        ).encode("utf-8")
        request = Request(
            self.api_url,
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
            content = payload["choices"][0]["message"]["content"]
            if not isinstance(content, str) or not content.strip():
                raise ValueError("provider returned no message content")
            return content.strip()
        except (OSError, URLError, TimeoutError, ValueError, KeyError, IndexError, TypeError):
            return (
                "The financial-education provider is temporarily unavailable. "
                "Please try again later."
            )


def get_assistant_adapter() -> AssistantAdapter:
    settings = get_settings()
    provider = str(getattr(settings, "ai_assistant_provider", "") or "").strip()
    if not provider or provider.lower() in {"none", "disabled"}:
        return NoProviderAdapter()
    if provider.lower() == "openai_compatible":
        api_url = str(getattr(settings, "ai_assistant_api_url", "") or "").strip()
        api_key = str(getattr(settings, "ai_assistant_api_key", "") or "").strip()
        model = str(getattr(settings, "ai_assistant_model", "") or "").strip()
        try:
            timeout = float(getattr(settings, "ai_assistant_timeout_seconds", 10))
        except (TypeError, ValueError):
            timeout = 0
        if not api_url or not api_key or not model or timeout <= 0:
            return NoProviderAdapter(
                "The AI provider is configured incompletely. "
                "Financial-education answers are unavailable."
            )
        return OpenAICompatibleAdapter(api_url, api_key, model, timeout)
    return ConfiguredProviderAdapter(provider)
