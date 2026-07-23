"""Anthropic provider adapter.

Thin wrapper around the official Anthropic SDK, normalizing responses
and exceptions into the gateway's shared types.
"""

import anthropic

from app.config.settings import settings
from providers.base import (
    GenerateParams,
    Provider,
    ProviderError,
    ProviderResponse,
    ProviderTimeoutError,
)


class AnthropicProvider(Provider):
    """Provider adapter for Anthropic's Claude models."""

    DEFAULT_MODEL = "claude-sonnet-4-20250514"

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self._api_key = api_key or settings.anthropic_api_key
        self._model = model or self.DEFAULT_MODEL

        if not self._api_key or self._api_key == "your-api-key-here":
            raise ProviderError(
                "ANTHROPIC_API_KEY is not set. Add it to your .env file.",
                provider="anthropic",
            )

        self._client = anthropic.AsyncAnthropic(api_key=self._api_key)

    async def generate(self, prompt: str, params: GenerateParams) -> ProviderResponse:
        try:
            message = await self._client.messages.create(
                model=self._model,
                max_tokens=params.max_tokens,
                temperature=params.temperature,
                messages=[{"role": "user", "content": prompt}],
            )

            # Extract text from the response content blocks
            text = "".join(
                block.text for block in message.content if block.type == "text"
            )

            tokens_used = (message.usage.input_tokens or 0) + (
                message.usage.output_tokens or 0
            )

            return ProviderResponse(
                text=text,
                tokens_used=tokens_used,
                raw={
                    "provider": "anthropic",
                    "model": message.model,
                    "stop_reason": message.stop_reason,
                    "usage": {
                        "input_tokens": message.usage.input_tokens,
                        "output_tokens": message.usage.output_tokens,
                    },
                },
            )

        except anthropic.APITimeoutError as exc:
            raise ProviderTimeoutError(
                message=str(exc), provider="anthropic"
            ) from exc

        except anthropic.AuthenticationError as exc:
            raise ProviderError(
                f"Authentication failed: {exc}", provider="anthropic"
            ) from exc

        except anthropic.RateLimitError as exc:
            raise ProviderError(
                f"Rate limited by Anthropic: {exc}", provider="anthropic"
            ) from exc

        except anthropic.APIError as exc:
            raise ProviderError(
                f"Anthropic API error: {exc}", provider="anthropic"
            ) from exc
