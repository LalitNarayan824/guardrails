"""POST /v1/generate — the main gateway endpoint.

Accepts a prompt, runs it through the input guardrail chain,
dispatches to the selected LLM provider, and returns a guarded response.
Output guardrails and retry loop come in Phase 2.
"""

from __future__ import annotations

import time

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from guardrails.base import GuardrailAction
from providers.base import GenerateParams, ProviderError
from providers.factory import get_provider

router = APIRouter()

# ---------------------------------------------------------------------------
# These will be injected at app startup (see main.py)
# ---------------------------------------------------------------------------
_input_chain = None


def set_input_chain(chain):
    """Called once from app startup to inject the loaded guardrail chain."""
    global _input_chain
    _input_chain = chain


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class GenerateRequest(BaseModel):
    """Incoming request body for /v1/generate."""

    prompt: str
    provider: str | None = None              # falls back to config default
    user_id: str = "anonymous"
    response_schema: dict | None = None      # optional JSON Schema
    policy_overrides: list[str] | None = None # future: disable specific rules


class GenerateResponse(BaseModel):
    """Response envelope — shape is fixed now, even if some fields are placeholders."""

    output: str | None
    blocked: bool
    retries_used: int
    guardrails_triggered: list[str]
    latency_ms: int
    cost_usd: float


# ---------------------------------------------------------------------------
# Route handler
# ---------------------------------------------------------------------------

@router.post("/v1/generate", response_model=GenerateResponse)
async def generate(req: GenerateRequest):
    start = time.perf_counter()
    context = {"user_id": req.user_id}

    # --- Input guardrails ---------------------------------------------------
    if _input_chain is not None:
        processed_prompt, triggered = await _input_chain.run(req.prompt, context)
        blocked = any(r.action == GuardrailAction.BLOCK for r in triggered)

        if blocked:
            latency = int((time.perf_counter() - start) * 1000)
            return GenerateResponse(
                output=None,
                blocked=True,
                retries_used=0,
                guardrails_triggered=[r.guardrail_name for r in triggered],
                latency_ms=latency,
                cost_usd=0.0,
            )
    else:
        processed_prompt = req.prompt
        triggered = []

    # --- Provider call -------------------------------------------------------
    try:
        provider = get_provider(req.provider)
        params = GenerateParams(response_schema=req.response_schema)
        result = await provider.generate(processed_prompt, params)
    except ProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    # --- Response (no output guardrails yet — Phase 2) -----------------------
    latency = int((time.perf_counter() - start) * 1000)
    return GenerateResponse(
        output=result.text,
        blocked=False,
        retries_used=0,
        guardrails_triggered=[r.guardrail_name for r in triggered],
        latency_ms=latency,
        cost_usd=0.0,  # real cost calc comes in Phase 3
    )
