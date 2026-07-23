"""Tests for the PIIGuardrail — redact and block modes."""

import pytest

from guardrails.base import GuardrailAction
from guardrails.pii import PIIGuardrail


@pytest.mark.asyncio
async def test_email_is_redacted():
    guard = PIIGuardrail()
    result = await guard.check("Contact me at john@example.com please", {})
    assert result.action == GuardrailAction.REDACT
    assert "[EMAIL_REDACTED]" in result.modified_input
    assert "john@example.com" not in result.modified_input


@pytest.mark.asyncio
async def test_phone_is_redacted():
    guard = PIIGuardrail()
    result = await guard.check("Call me at 555-123-4567", {})
    assert result.action == GuardrailAction.REDACT
    assert "[PHONE_REDACTED]" in result.modified_input


@pytest.mark.asyncio
async def test_credit_card_is_redacted():
    guard = PIIGuardrail()
    result = await guard.check("My card is 4111 1111 1111 1111", {})
    assert result.action == GuardrailAction.REDACT
    assert "[CREDIT_CARD_REDACTED]" in result.modified_input


@pytest.mark.asyncio
async def test_clean_text_passes():
    guard = PIIGuardrail()
    result = await guard.check("Tell me a joke about cats", {})
    assert result.action == GuardrailAction.PASS
    assert result.modified_input is None


@pytest.mark.asyncio
async def test_block_mode_blocks_on_pii():
    guard = PIIGuardrail(action=GuardrailAction.BLOCK)
    result = await guard.check("My email is test@example.com", {})
    assert result.action == GuardrailAction.BLOCK
    assert result.modified_input is None


@pytest.mark.asyncio
async def test_only_specified_entities_detected():
    guard = PIIGuardrail(entities=["EMAIL"])
    text = "Email john@test.com, phone 555-123-4567"
    result = await guard.check(text, {})
    assert result.action == GuardrailAction.REDACT
    assert "[EMAIL_REDACTED]" in result.modified_input
    assert "555-123-4567" in result.modified_input  # phone not touched
