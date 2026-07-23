"""Rate limiter — Redis-backed fixed-window counter per user.

Uses a simple INCR + EXPIRE pattern (fixed-window). Good enough for
Phase 1; a true sliding-window or token bucket is noted as a possible
later upgrade.
"""

from guardrails.base import Guardrail, GuardrailAction, GuardrailResult


class RateLimiter(Guardrail):
    """Block requests that exceed a per-user rate limit within a time window."""

    name = "rate_limit"

    def __init__(
        self,
        redis_client,
        max_requests: int = 20,
        window_seconds: int = 60,
    ) -> None:
        self.redis = redis_client
        self.max_requests = max_requests
        self.window = window_seconds

    async def check(self, payload: str, context: dict) -> GuardrailResult:
        user_id = context.get("user_id", "anonymous")
        key = f"rate:{user_id}"

        count = await self.redis.incr(key)
        if count == 1:
            # First request in this window — set expiry
            await self.redis.expire(key, self.window)

        if count > self.max_requests:
            return GuardrailResult(
                action=GuardrailAction.BLOCK,
                guardrail_name=self.name,
                reason=f"Rate limit exceeded ({self.max_requests} requests per {self.window}s)",
            )

        return GuardrailResult(
            action=GuardrailAction.PASS,
            guardrail_name=self.name,
        )
