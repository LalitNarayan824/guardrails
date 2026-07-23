"""Tests for the RateLimiter guardrail using fakeredis."""

import pytest
import fakeredis.aioredis

from guardrails.base import GuardrailAction
from guardrails.rate_limit import RateLimiter


@pytest.fixture
async def redis_client():
    """Create a fresh fakeredis async client for each test."""
    client = fakeredis.aioredis.FakeRedis()
    yield client
    await client.flushall()
    await client.aclose()


@pytest.mark.asyncio
async def test_requests_within_limit_pass(redis_client):
    limiter = RateLimiter(redis_client, max_requests=5, window_seconds=60)
    context = {"user_id": "user1"}

    for _ in range(5):
        result = await limiter.check("hello", context)
        assert result.action == GuardrailAction.PASS


@pytest.mark.asyncio
async def test_request_over_limit_is_blocked(redis_client):
    limiter = RateLimiter(redis_client, max_requests=3, window_seconds=60)
    context = {"user_id": "user2"}

    # First 3 pass
    for _ in range(3):
        result = await limiter.check("hello", context)
        assert result.action == GuardrailAction.PASS

    # 4th is blocked
    result = await limiter.check("hello", context)
    assert result.action == GuardrailAction.BLOCK
    assert "Rate limit exceeded" in result.reason


@pytest.mark.asyncio
async def test_different_users_have_separate_limits(redis_client):
    limiter = RateLimiter(redis_client, max_requests=2, window_seconds=60)

    # User A uses both requests
    for _ in range(2):
        result = await limiter.check("hello", {"user_id": "userA"})
        assert result.action == GuardrailAction.PASS

    # User A is now blocked
    result = await limiter.check("hello", {"user_id": "userA"})
    assert result.action == GuardrailAction.BLOCK

    # User B still has their full quota
    result = await limiter.check("hello", {"user_id": "userB"})
    assert result.action == GuardrailAction.PASS


@pytest.mark.asyncio
async def test_anonymous_user_when_no_user_id(redis_client):
    limiter = RateLimiter(redis_client, max_requests=1, window_seconds=60)

    result = await limiter.check("hello", {})  # no user_id
    assert result.action == GuardrailAction.PASS

    result = await limiter.check("hello", {})
    assert result.action == GuardrailAction.BLOCK
