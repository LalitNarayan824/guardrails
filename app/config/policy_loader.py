"""YAML Policy Engine — loads rules at startup, maps rule type → Guardrail instance.

Reads ``config/policies.yaml``, instantiates the appropriate Guardrail for each
rule, and returns a ready-to-use GuardrailChain.  No hot-reload yet (Phase 3).
"""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

from guardrails.base import Guardrail, GuardrailAction
from guardrails.chain import GuardrailChain
from guardrails.length_guard import LengthGuard
from guardrails.pii import PIIGuardrail
from guardrails.rate_limit import RateLimiter

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Registry: maps YAML ``guardrail`` field → builder function
# ---------------------------------------------------------------------------

# Each builder receives the full rule dict and the shared redis client,
# and returns a Guardrail instance.

BuilderFn = type(lambda rule, redis: None)  # just for readability


def _build_pii(rule: dict, redis_client) -> Guardrail:
    action = GuardrailAction(rule.get("action", "redact"))
    entities = rule.get("entities")
    return PIIGuardrail(action=action, entities=entities)


def _build_length_guard(rule: dict, redis_client) -> Guardrail:
    return LengthGuard(max_tokens=rule.get("max_tokens", 4000))


def _build_rate_limit(rule: dict, redis_client) -> Guardrail | None:
    if redis_client is None:
        logger.warning("Skipping rate_limit guardrail — Redis is not available")
        return None
    return RateLimiter(
        redis_client=redis_client,
        max_requests=rule.get("max_requests", 20),
        window_seconds=rule.get("window_seconds", 60),
    )


GUARDRAIL_REGISTRY: dict[str, BuilderFn] = {
    "pii_detection": _build_pii,
    "length_guard": _build_length_guard,
    "rate_limit": _build_rate_limit,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_guardrail_chain(
    config_path: str,
    redis_client=None,
    stage: str = "input",
) -> GuardrailChain:
    """Parse ``config_path`` and build a GuardrailChain for the given stage.

    Parameters
    ----------
    config_path : str
        Path to the YAML policy file.
    redis_client :
        Async Redis client instance (needed by rate_limit guardrail).
    stage : str
        ``"input"`` or ``"output"`` — only rules matching this stage are loaded.

    Returns
    -------
    GuardrailChain
        Ready-to-run chain with guardrails in YAML-defined order.
    """
    path = Path(config_path)
    if not path.exists():
        logger.warning("Policy file not found at %s — returning empty chain", path)
        return GuardrailChain([])

    with open(path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    rules = config.get("rules", [])
    guardrails: list[Guardrail] = []

    for rule in rules:
        rule_name = rule.get("name", "<unnamed>")
        rule_type = rule.get("type", "")
        guardrail_key = rule.get("guardrail", "")

        # Only load rules for the requested stage
        if rule_type != stage:
            continue

        builder = GUARDRAIL_REGISTRY.get(guardrail_key)
        if builder is None:
            logger.warning(
                "Unknown guardrail '%s' in rule '%s' — skipping",
                guardrail_key,
                rule_name,
            )
            continue

        try:
            guardrail = builder(rule, redis_client)
            if guardrail is not None:
                guardrails.append(guardrail)
                logger.info("Loaded guardrail: %s (rule: %s)", guardrail_key, rule_name)
        except Exception:
            logger.exception("Failed to build guardrail for rule '%s'", rule_name)

    logger.info(
        "Built %s-stage chain with %d guardrail(s)", stage, len(guardrails)
    )
    return GuardrailChain(guardrails)
