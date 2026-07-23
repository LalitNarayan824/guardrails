"""Local mock provider for testing and development.

Supports multiple modes so later phases (retry loop, circuit breaker)
can force specific behaviors without hitting a real LLM.
"""

import asyncio
import json
from typing import Literal

from providers.base import (
    GenerateParams,
    Provider,
    ProviderError,
    ProviderResponse,
    ProviderTimeoutError,
)


class LocalMockProvider(Provider):
    """Deterministic mock LLM provider.

    Modes
    -----
    valid       — returns clean text (or valid JSON when a response_schema is provided).
    broken_json — returns syntactically broken JSON (for retry-loop testing in Phase 2).
    timeout     — sleeps past any reasonable latency budget (for circuit-breaker testing).
    error       — raises a ProviderError immediately (for fallback-response testing).
    """

    VALID_TEXT = "This is a mock response from the local provider."
    VALID_JSON_TEMPLATE = {"message": "Mock response", "status": "success"}
    BROKEN_JSON = '{"message": "incomplete json, "status": broken}'
    TIMEOUT_SECONDS = 30  # intentionally long; callers should time out before this

    def __init__(
        self,
        mode: Literal["valid", "broken_json", "timeout", "error"] = "valid",
    ):
        self.mode = mode

    async def generate(self, prompt: str, params: GenerateParams) -> ProviderResponse:
        if self.mode == "valid":
            return self._valid_response(prompt, params)

        if self.mode == "broken_json":
            return self._broken_json_response(prompt)

        if self.mode == "timeout":
            await asyncio.sleep(self.TIMEOUT_SECONDS)
            # If we somehow reach here, still return something
            return self._valid_response(prompt, params)

        if self.mode == "error":
            raise ProviderError("Simulated provider failure", provider="local")

        raise ProviderError(
            f"Unknown mode: {self.mode}", provider="local"
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _valid_response(
        self, prompt: str, params: GenerateParams
    ) -> ProviderResponse:
        """Return clean text or valid JSON depending on whether a schema was requested."""
        if params.response_schema is not None:
            text = json.dumps(self.VALID_JSON_TEMPLATE)
        else:
            text = self.VALID_TEXT

        return ProviderResponse(
            text=text,
            tokens_used=len(text.split()),
            raw={"provider": "local", "mode": self.mode, "prompt_preview": prompt[:80]},
        )

    def _broken_json_response(self, prompt: str) -> ProviderResponse:
        """Return intentionally malformed JSON."""
        return ProviderResponse(
            text=self.BROKEN_JSON,
            tokens_used=len(self.BROKEN_JSON.split()),
            raw={"provider": "local", "mode": "broken_json", "prompt_preview": prompt[:80]},
        )
