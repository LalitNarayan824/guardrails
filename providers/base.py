"""Provider base classes and shared types.

Defines the contract every LLM adapter must satisfy so gateway logic
never needs to know which provider it's talking to.
"""

from abc import ABC, abstractmethod

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Shared request / response models
# ---------------------------------------------------------------------------

class GenerateParams(BaseModel):
    """Normalized parameters passed to every provider."""

    max_tokens: int = 1024
    temperature: float = 0.7
    response_schema: dict | None = None


class ProviderResponse(BaseModel):
    """Normalized response returned by every provider."""

    text: str
    tokens_used: int
    raw: dict  # original provider payload, for debugging/logging


# ---------------------------------------------------------------------------
# Exceptions — downstream code catches these, never provider-specific errors
# ---------------------------------------------------------------------------

class ProviderError(Exception):
    """Generic error from a provider (bad request, auth failure, etc.)."""

    def __init__(self, message: str, provider: str = "unknown"):
        self.provider = provider
        super().__init__(f"[{provider}] {message}")


class ProviderTimeoutError(ProviderError):
    """Provider call exceeded the latency budget."""

    def __init__(self, message: str = "Request timed out", provider: str = "unknown"):
        super().__init__(message, provider)


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class Provider(ABC):
    """Abstract base for all LLM provider adapters."""

    @abstractmethod
    async def generate(self, prompt: str, params: GenerateParams) -> ProviderResponse:
        """Send prompt to the underlying LLM and return a normalized response."""
        ...
