"""GuardrailChain — ordered executor with short-circuit semantics.

Runs guardrails in sequence (cheapest first). Short-circuits on the
first ``BLOCK`` verdict; accumulates ``REDACT`` mutations so downstream
guardrails and the LLM provider see the redacted payload.
"""

from guardrails.base import Guardrail, GuardrailAction, GuardrailResult


class GuardrailChain:
    """Execute an ordered list of guardrails against a payload."""

    def __init__(self, guardrails: list[Guardrail]) -> None:
        self.guardrails = guardrails  # order matters: cheapest first

    async def run(
        self, payload: str, context: dict
    ) -> tuple[str, list[GuardrailResult]]:
        """Run all guardrails in order.

        Returns
        -------
        tuple[str, list[GuardrailResult]]
            (final_payload, list_of_triggered_results)
            - If any guardrail blocks, the list's last item is the blocking result.
            - ``final_payload`` reflects all accumulated REDACT mutations.
        """
        triggered: list[GuardrailResult] = []
        current_payload = payload

        for guardrail in self.guardrails:
            result = await guardrail.check(current_payload, context)

            if result.action == GuardrailAction.BLOCK:
                triggered.append(result)
                return current_payload, triggered  # short-circuit

            if result.action == GuardrailAction.REDACT:
                current_payload = result.modified_input or current_payload
                triggered.append(result)

            # PASS results are not added to triggered — only actual
            # interventions show up in the response's guardrails_triggered.

        return current_payload, triggered
