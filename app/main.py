"""FastAPI application factory — creates and configures the gateway app."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import redis.asyncio as aioredis

from fastapi import FastAPI

from app.config.settings import settings
from app.config.policy_loader import load_guardrail_chain
from app.routers import health
from app.routers.generate import router as generate_router, set_input_chain

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle.

    - Connects to Redis.
    - Loads the YAML policy config and builds the input guardrail chain.
    - Injects the chain into the generate router.
    """
    # --- Startup -------------------------------------------------------------
    # Try connecting to Redis; if unavailable, rate limiting is disabled
    redis_client = None
    try:
        redis_client = aioredis.from_url(
            settings.redis_url, decode_responses=True
        )
        await redis_client.ping()
        logger.info("Connected to Redis at %s", settings.redis_url)
    except Exception as exc:
        logger.warning(
            "Redis unavailable (%s) — rate limiting will be disabled. "
            "Start Redis or use docker-compose for full functionality.",
            exc,
        )
        redis_client = None

    input_chain = load_guardrail_chain(
        config_path=settings.policy_config_path,
        redis_client=redis_client,
        stage="input",
    )
    set_input_chain(input_chain)
    logger.info("Input guardrail chain loaded")

    yield  # app is running

    # --- Shutdown ------------------------------------------------------------
    await redis_client.aclose()
    logger.info("Redis connection closed")


def create_app() -> FastAPI:
    """Application factory — creates and configures the FastAPI app."""
    app = FastAPI(
        title="LLM Guardrails Gateway",
        description="Middleware proxy enforcing safety, compliance, and structural guardrails on LLM traffic.",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Mount routers
    app.include_router(health.router, tags=["health"])
    app.include_router(generate_router, tags=["generate"])

    return app


app = create_app()
