"""Provider factory — Strategy pattern for provider selection.

Provider is selected via the `provider` field on the incoming request,
falling back to a config default if omitted.
"""

from __future__ import annotations

from app.config.settings import settings
from providers.base import Provider, ProviderError
from providers.local_mock import LocalMockProvider


def get_provider(name: str | None = None) -> Provider:
    """Return the appropriate Provider instance for the given name.

    Falls back to ``settings.default_provider`` when *name* is ``None``.
    Raises ``ProviderError`` if the name is not recognized.
    """
    resolved_name = name or settings.default_provider

    if resolved_name == "local":
        return LocalMockProvider()

    if resolved_name == "anthropic":
        # Lazy import so the gateway doesn't crash at startup when no
        # Anthropic API key is configured and the user only uses "local".
        from providers.anthropic_provider import AnthropicProvider

        return AnthropicProvider()

    raise ProviderError(
        f"Unknown provider: '{resolved_name}'. Available: ['local', 'anthropic']",
        provider=resolved_name,
    )
