"""Provider factory — Strategy pattern for provider selection.

Provider is selected via the `provider` field on the incoming request,
falling back to a config default if omitted.
"""

from providers.base import Provider, ProviderError
from providers.local_mock import LocalMockProvider


def get_provider(name: str) -> Provider:
    """Return the appropriate Provider instance for the given name.

    Raises ProviderError if the name is not recognized.
    """
    providers: dict[str, Provider] = {
        "local": LocalMockProvider(),
    }

    provider = providers.get(name)
    if provider is None:
        raise ProviderError(
            f"Unknown provider: '{name}'. Available: {list(providers.keys())}",
            provider=name,
        )
    return provider
