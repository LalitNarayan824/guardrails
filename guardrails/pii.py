"""PII detection guardrail — regex-based, supports redact and block modes.

Detects emails, phone numbers, and credit card numbers using regex patterns.
Presidio/spaCy for names/addresses is deliberately out of scope for Phase 1.
"""

import re

from guardrails.base import Guardrail, GuardrailAction, GuardrailResult

# Patterns map entity name → compiled regex
PATTERNS: dict[str, re.Pattern] = {
    "EMAIL": re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
    "PHONE": re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b"),
    "CREDIT_CARD": re.compile(r"\b(?:\d[ -]*?){13,16}\b"),
    "SSN": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
}


class PIIGuardrail(Guardrail):
    """Detect and optionally redact PII from the input payload.

    Parameters
    ----------
    action : GuardrailAction
        REDACT (default) — replace PII with ``[ENTITY_REDACTED]`` tokens.
        BLOCK — reject the request outright if any PII is found.
    entities : list[str] | None
        Which entity types to scan for.  Defaults to all known patterns.
    """

    name = "pii_detection"

    def __init__(
        self,
        action: GuardrailAction = GuardrailAction.REDACT,
        entities: list[str] | None = None,
    ) -> None:
        self.action = action
        self.entities = entities or list(PATTERNS.keys())

    async def check(self, payload: str, context: dict) -> GuardrailResult:
        modified = payload
        found: list[str] = []

        for entity in self.entities:
            pattern = PATTERNS.get(entity)
            if pattern is None:
                continue

            if pattern.search(modified):
                found.append(entity)
                if self.action == GuardrailAction.REDACT:
                    modified = pattern.sub(f"[{entity}_REDACTED]", modified)

        if not found:
            return GuardrailResult(
                action=GuardrailAction.PASS,
                guardrail_name=self.name,
            )

        return GuardrailResult(
            action=self.action,
            guardrail_name=self.name,
            modified_input=modified if self.action == GuardrailAction.REDACT else None,
            reason=f"Detected: {', '.join(found)}",
        )
