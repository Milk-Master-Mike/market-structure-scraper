from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MARKET_STRUCTURE_", env_file=".env.local", extra="ignore"
    )

    user_agent: str | None = None
    cache_dir: Path = Path(".cache/market-structure-scraper")
    cache_ttl_seconds: int = Field(default=3600, ge=60)
    max_concurrency: int = Field(default=2, ge=1, le=4)
    requests_per_second: float = Field(default=4.0, gt=0, le=5)
    timeout_seconds: float = Field(default=20.0, gt=0, le=60)

    def validated_user_agent(self) -> str:
        value = (self.user_agent or "").strip()
        if "@" not in value or len(value) < 12:
            raise ValueError(
                "Live collection requires MARKET_STRUCTURE_USER_AGENT with an "
                "application name and monitored email address."
            )
        return value

