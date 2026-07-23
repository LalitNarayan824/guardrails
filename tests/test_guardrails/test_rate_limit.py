"""Tests for the RateLimiter guardrail using fakeredis."""

import pytest
import fakeredis.aioredis

from guardrails.base import GuardrailAction
from guardrails.rate_limit import RateLimiter


@pytest.fixture
async def redis_client():
    client = fakeredis.aioredis.FakeRedis()
    yield client
    await client.flushall()
    await client.aclose()


@pytest.mark.asyncio
async def test_requests_within_limit_pass(redis_client):
    limiter = RateLimiter(redis_client, max_requests=5, window_seconds=60)
    for _ in range(5):
        result = await limiter.check("hello", {"user_id": "u1"})
        assert result.action == GuardrailAction.PASS


@pytest.mark.asyncio
async def test_request_over_limit_is_blocked(redis_client):
    limiter = RateLimiter(redis_client, max_requests=3, window_seconds=60)
    for _ in range(3):
        await limiter.check("hello", {"user_id": "u2"})

    result = await limiter.check("hello", {"user_id": "u2"})
    assert result.action == GuardrailAction.BLOCK
    assert "Rate limit exceeded" in result.reason


@pytest.mark.asyncio
async def test_different_users_have_separate_limits(redis_client):
    limiter = RateLimiter(redis_client, max_requests=1, window_seconds=60)

    result = await limiter.check("hello", {"user_id": "userA"})
    assert result.action == GuardrailAction.PASS

    result = await limiter.check("hello", {"user_id": "userA"})
    assert result.action == GuardrailAction.BLOCK

    # User B still has quota
    result = await limiter.check("hello", {"user_id": "userB"})
    assert result.action == GuardrailAction.PASS
