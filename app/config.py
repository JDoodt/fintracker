from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    SECRET_KEY: str = "dev-secret-key-change-in-production-please"
    DATABASE_URL: str = "sqlite:///data/finance.db"
    SESSION_COOKIE_NAME: str = "fintracker_session"
    SESSION_MAX_AGE: int = 30 * 24 * 3600  # 30 days in seconds
    RATE_LIMIT_MAX_ATTEMPTS: int = 3
    RATE_LIMIT_LOCKOUT_SECONDS: int = 300  # 5 minutes


settings = Settings()
