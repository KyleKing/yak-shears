"""Configuration management for the research platform."""

from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/research_platform"
    database_echo: bool = False

    # API Keys
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    groq_api_key: Optional[str] = None

    # Embedding Service
    embedding_model: str = "openai:text-embedding-3-small"
    embedding_dimensions: int = 1536

    # Logfire
    logfire_token: Optional[str] = None
    logfire_project: str = "agent-research-platform"

    # Agent Defaults
    default_model: str = "openai:gpt-4"
    max_retries: int = 3
    timeout_seconds: int = 30

    # Evaluation
    eval_cache_enabled: bool = True
    eval_record_mode: str = "once"  # once, rewrite, new_episodes, none

    # Feature Flags
    enable_logfire: bool = True
    enable_cost_tracking: bool = True

    @property
    def db_url_sync(self) -> str:
        """Synchronous database URL (for Alembic)."""
        return self.database_url.replace("+asyncpg", "")


# Global settings instance
settings = Settings()
