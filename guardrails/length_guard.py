"""Length / cost guard — blocks oversized prompts before they reach a paid LLM API.

Uses a rough ``len(text) // 4`` token estimator (swap for tiktoken later
if precision matters).
"""

from guardrails.base import Guardrail, GuardrailAction, GuardrailResult


class LengthGuard(Guardrail):
    """Block prompts that exceed a configurable token estimate."""

    name = "length_guard"

    def __init__(self, max_tokens: int = 4000) -> None:
        self.max_tokens = max_tokens

    async def check(self, payload: str, context: dict) -> GuardrailResult:
        estimate = len(payload) // 4  # rough chars-to-tokens

        if estimate > self.max_tokens:
            return GuardrailResult(
                action=GuardrailAction.BLOCK,
                guardrail_name=self.name,
                reason=f"Input exceeds {self.max_tokens} token estimate ({estimate} estimated)",
            )

        return GuardrailResult(
            action=GuardrailAction.PASS,
            guardrail_name=self.name,
        )
