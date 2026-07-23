from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    redis_url: str = "redis://localhost:6379/0"
    default_provider: str = "local"
    anthropic_api_key: str = ""
    policy_config_path: str = "./config/policies.yaml"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
