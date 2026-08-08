from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables / .env file."""

    DATABASE_URL: str
    RABBITMQ_URL: str
    OPENAI_API_KEY: str
    GNEWS_API_KEY: str
    GNEWS_RATE_LIMIT: int = 100       # Max articles to fetch per day
    WORKER_SLEEP_SECONDS: int = 2     # Seconds to wait between AI analysis jobs

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
