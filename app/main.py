from fastapi import FastAPI

from app.routers import health


def create_app() -> FastAPI:
    """Application factory — creates and configures the FastAPI app."""
    app = FastAPI(
        title="LLM Guardrails Gateway",
        description="Middleware proxy enforcing safety, compliance, and structural guardrails on LLM traffic.",
        version="0.1.0",
    )

    # Mount routers
    app.include_router(health.router, tags=["health"])

    return app


app = create_app()
