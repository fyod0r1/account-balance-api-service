from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = Field(
        default="postgresql+asyncpg://account_balance:account_balance@localhost:5432/account_balance"
    )
    jwt_secret_key: str = "change-me-use-at-least-32-bytes-secret"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    payment_webhook_secret: str = "gfdmhghif38yrf9ew0jkf32"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
