"""Tests for the Provider interface and LocalMockProvider."""

import asyncio

import pytest

from providers.base import GenerateParams, ProviderError, ProviderResponse
from providers.local_mock import LocalMockProvider


# ---------------------------------------------------------------------------
# LocalMockProvider — mode: valid
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_valid_mode_returns_text():
    provider = LocalMockProvider(mode="valid")
    result = await provider.generate("Tell me a joke", GenerateParams())

    assert isinstance(result, ProviderResponse)
    assert result.text == LocalMockProvider.VALID_TEXT
    assert result.tokens_used > 0
    assert result.raw["provider"] == "local"
    assert result.raw["mode"] == "valid"


@pytest.mark.asyncio
async def test_valid_mode_returns_json_when_schema_set():
    provider = LocalMockProvider(mode="valid")
    params = GenerateParams(response_schema={"type": "object"})
    result = await provider.generate("Give me JSON", params)

    assert '"message"' in result.text
    assert '"status"' in result.text


@pytest.mark.asyncio
async def test_default_mode_is_valid():
    provider = LocalMockProvider()
    result = await provider.generate("Hello", GenerateParams())
    assert result.text == LocalMockProvider.VALID_TEXT


# ---------------------------------------------------------------------------
# LocalMockProvider — mode: broken_json
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_broken_json_mode_returns_malformed_json():
    provider = LocalMockProvider(mode="broken_json")
    result = await provider.generate("Give me JSON", GenerateParams())

    assert result.text == LocalMockProvider.BROKEN_JSON
    # Verify it's actually broken
    with pytest.raises(Exception):
        import json
        json.loads(result.text)


# ---------------------------------------------------------------------------
# LocalMockProvider — mode: error
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_error_mode_raises_provider_error():
    provider = LocalMockProvider(mode="error")

    with pytest.raises(ProviderError, match="Simulated provider failure"):
        await provider.generate("Hello", GenerateParams())


# ---------------------------------------------------------------------------
# LocalMockProvider — mode: timeout
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_timeout_mode_is_slow():
    """Verify timeout mode actually blocks (we cancel it quickly to avoid waiting 30s)."""
    provider = LocalMockProvider(mode="timeout")

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(
            provider.generate("Hello", GenerateParams()),
            timeout=0.1,
        )


# ---------------------------------------------------------------------------
# Provider factory
# ---------------------------------------------------------------------------

def test_factory_returns_local_provider():
    from providers.factory import get_provider

    provider = get_provider("local")
    assert isinstance(provider, LocalMockProvider)


def test_factory_raises_on_unknown_provider():
    from providers.factory import get_provider

    with pytest.raises(ProviderError, match="Unknown provider"):
        get_provider("nonexistent")


def test_factory_falls_back_to_default_provider(monkeypatch):
    """When no name is given, factory uses settings.default_provider."""
    from providers import factory

    monkeypatch.setattr(factory.settings, "default_provider", "local")
    provider = factory.get_provider(None)
    assert isinstance(provider, LocalMockProvider)


def test_factory_anthropic_fails_without_api_key(monkeypatch):
    """Anthropic provider should raise ProviderError when API key is missing."""
    from providers import factory

    monkeypatch.setattr(factory.settings, "anthropic_api_key", "")
    with pytest.raises(ProviderError, match="ANTHROPIC_API_KEY is not set"):
        factory.get_provider("anthropic")

