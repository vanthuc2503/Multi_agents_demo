"""Production config — 12-Factor: tất cả từ environment variables."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    environment: str = "development"
    log_level: str = "INFO"
    debug: bool = False

    # App
    app_name: str = "Production AI Agent"
    app_version: str = "1.0.0"

    # LLM (OpenAI)
    openai_api_key: str = ""
    llm_model: str = "gpt-4o-mini"

    # Storage (stateless)
    # Railway Redis thường inject `REDIS_URL`
    redis_url: str = Field(default="redis://localhost:6379/0", validation_alias="REDIS_URL")

    # CORS
    allowed_origins: str = "*"

    # Security
    agent_api_key: str = "dev-key-change-me-in-production"

    # Rate limiting
    rate_limit_per_minute: int = 10

    # Cost guard
    monthly_budget_usd: float = 10.0

    # Conversation
    history_max_messages: int = 20


settings = Settings()
