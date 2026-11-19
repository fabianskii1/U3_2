from functools import lru_cache
from urllib.parse import quote

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str | None = None
    postgres_user: str | None = None
    postgres_password: str | None = None
    postgres_db: str | None = None
    db_host: str = "127.0.0.1"
    db_port: int = 5433
    cors_origins: list[str] = ["http://127.0.0.1:5173", "http://localhost:5173"]
    ai_base_url: str = "http://127.0.0.1:8001"
    alarm_ingest_token: SecretStr | None = None

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def resolve_database_url(self) -> "Settings":
        if self.database_url:
            return self
        if not all((self.postgres_user, self.postgres_password, self.postgres_db)):
            raise ValueError("DATABASE_URL or POSTGRES_USER/PASSWORD/DB is required")
        user = quote(self.postgres_user, safe="")
        password = quote(self.postgres_password, safe="")
        database = quote(self.postgres_db, safe="")
        self.database_url = (
            f"postgresql+asyncpg://{user}:{password}@{self.db_host}:{self.db_port}/{database}"
        )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
