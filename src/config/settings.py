"""Configuration management for Discord Research Assistant."""
from typing import Literal
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # Discord
    discord_token: str = Field(..., description="Discord Bot Token")
    sync_commands: bool = Field(True, description="Sync slash commands on startup")
    command_scope: Literal["global", "guild"] = Field("global", description="Command registration scope")
    command_guild_ids: str = Field("", description="Comma-separated guild IDs for guild commands")

    # OpenAI / LLM
    openai_base_url: str = Field("https://api.openai.com/v1", description="OpenAI API or vLLM endpoint")
    openai_api_key: str = Field(..., description="OpenAI API key")
    openai_model: str = Field("gpt-4o-mini", description="Main summarization model")
    openai_model_pre: str = Field("gpt-4o-mini", description="Pre-processing model")
    openai_model_val: str = Field("gpt-4o-mini", description="Validation model")
    llm_temperature: float = Field(0.2, description="Generation temperature")
    llm_max_output_tokens: int = Field(800, description="Max output tokens")

    # Redis
    redis_url: str = Field("redis://localhost:6379/0", description="Redis connection URL")

    # Scheduler
    monthly_push_cron: str = Field("0 9 1 * *", description="Monthly push cron expression")
    timezone: str = Field("Asia/Taipei", description="Timezone for scheduler")
    run_scheduler: bool = Field(True, description="Enable monthly push scheduler")
    top_papers_channel_id: str = Field("", description="Channel ID for monthly announcements")

    # Semantic Scholar
    s2_api_key: str = Field("", description="Semantic Scholar API key (optional)")

    # Rate Limits
    rate_limit_default_per_min: int = Field(3, description="Default rate limit per minute")
    rate_limit_default_per_day: int = Field(20, description="Default rate limit per day")
    rate_limit_trusted_per_min: int = Field(6, description="Trusted rate limit per minute")
    rate_limit_trusted_per_day: int = Field(100, description="Trusted rate limit per day")

    @property
    def guild_ids(self) -> list[int]:
        """Parse guild IDs from comma-separated string."""
        if not self.command_guild_ids:
            return []
        return [int(gid.strip()) for gid in self.command_guild_ids.split(",") if gid.strip()]


# Global settings instance
settings = Settings()
