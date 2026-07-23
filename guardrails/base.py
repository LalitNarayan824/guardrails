"""Guardrail base classes and shared types.

Defines the contract every guardrail rule must satisfy so the chain
executor can run them uniformly without knowing the implementation.
"""

from abc import ABC, abstractmethod
from enum import Enum

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Shared types
# ---------------------------------------------------------------------------

class GuardrailAction(str, Enum):
    """Possible verdicts from a guardrail check."""

    PASS = "pass"
    BLOCK = "block"
    REDACT = "redact"
    RETRY = "retry"  # output-side only, used in Phase 2


class GuardrailResult(BaseModel):
    """Result of a single guardrail check."""

    action: GuardrailAction
    guardrail_name: str
    modified_input: str | None = None  # set when action == REDACT
    reason: str | None = None          # set when action == BLOCK or RETRY


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class Guardrail(ABC):
    """Abstract base for all guardrail rules.

    Guardrails are stateless and side-effect-free beyond returning a
    GuardrailResult — this keeps them independently unit-testable.
    """

    name: str

    @abstractmethod
    async def check(self, payload: str, context: dict) -> GuardrailResult:
        """Evaluate the payload and return a pass/block/redact verdict.

        Parameters
        ----------
        payload : str
            The prompt text (input guardrails) or response text (output guardrails).
        context : dict
            Request-scoped info (e.g. ``user_id``, ``session_id``) so guardrails
            needing it (rate limiting, cost tracking) don't need a different
            method signature.
        """
        ...
