from typing import Literal

from pydantic import computed_field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    SERVICE_TYPE: Literal["api", "ingestion", "migration"] = "api"

    DATABASE_HOST: str = "db"
    DATABASE_PORT: int = 5432
    DATABASE_NAME: str = "mydatabase"

    API_USER_USERNAME: str = "api_user"
    API_USER_PASSWORD: str = "api_password"

    INGESTION_USER_USERNAME: str = "ingestion_user"
    INGESTION_USER_PASSWORD: str = "ingestion_password"

    MIGRATION_DB_USER: str = "alembic_user"
    MIGRATOR_PASSWORD: str = "alembic_password"

    ADMIN_USER: str
    ADMIN_PASSWORD: str

    REDIS_HOST: str = "redis"

    @computed_field
    @property
    def API_DATABASE_URL(self) -> str:
        return (
            f"postgresql+asyncpg://{self.API_USER_USERNAME}:"
            f"{self.API_USER_PASSWORD}@{self.DATABASE_HOST}:"
            f"{self.DATABASE_PORT}/{self.DATABASE_NAME}"
        )

    @computed_field
    @property
    def MIGRATION_DATABASE_URL(self) -> str:
        return (
            f"postgresql://{self.MIGRATION_DB_USER}:"
            f"{self.MIGRATOR_PASSWORD}@localhost:"
            f"{self.DATABASE_PORT}/{self.DATABASE_NAME}"
        )

    @computed_field
    @property
    def INGESTION_DATABASE_URL(self) -> str:
        return (
            f"postgresql+asyncpg://{self.INGESTION_USER_USERNAME}:"
            f"{self.INGESTION_USER_PASSWORD}@{self.DATABASE_HOST}:"
            f"{self.DATABASE_PORT}/{self.DATABASE_NAME}"
        )

    @computed_field
    @property
    def DATABASE_URL(self) -> str:
        if self.SERVICE_TYPE == "ingestion":
            return self.INGESTION_DATABASE_URL
        return self.API_DATABASE_URL

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
