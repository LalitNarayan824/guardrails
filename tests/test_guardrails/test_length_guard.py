"""Tests for the LengthGuard guardrail."""

import pytest

from guardrails.base import GuardrailAction
from guardrails.length_guard import LengthGuard


@pytest.mark.asyncio
async def test_short_prompt_passes():
    guard = LengthGuard(max_tokens=100)
    result = await guard.check("Hello world", {})

    assert result.action == GuardrailAction.PASS
    assert result.guardrail_name == "length_guard"


@pytest.mark.asyncio
async def test_oversized_prompt_is_blocked():
    guard = LengthGuard(max_tokens=10)
    prompt = "x" * 200  # 200 chars ÷ 4 = 50 tokens → exceeds 10
    result = await guard.check(prompt, {})

    assert result.action == GuardrailAction.BLOCK
    assert "exceeds" in result.reason


@pytest.mark.asyncio
async def test_exact_boundary_passes():
    guard = LengthGuard(max_tokens=10)
    prompt = "x" * 40  # 40 chars ÷ 4 = 10 tokens → exactly at limit
    result = await guard.check(prompt, {})

    assert result.action == GuardrailAction.PASS
