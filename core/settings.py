from pydantic import computed_field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_HOST: str = "localhost"
    DATABASE_PORT: int = 5432
    DATABASE_NAME: str = "mydatabase"
    DATABASE_USER: str = "user"
    DATABASE_PASSWORD: str = "password"

    MIGRATION_DB_USER: str = "alembic_user"
    MIGRATION_DB_PASSWORD: str = "alembic_password"

    @computed_field
    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+asyncpg://{self.DATABASE_USER}:"
            f"{self.DATABASE_PASSWORD}@{self.DATABASE_HOST}:"
            f"{self.DATABASE_PORT}/{self.DATABASE_NAME}"
        )

    @computed_field
    @property
    def MIGRATION_DATABASE_URL(self) -> str:
        return (
            f"postgresql://{self.MIGRATION_DB_USER}:"
            f"{self.MIGRATION_DB_PASSWORD}@{self.DATABASE_HOST}:"
            f"{self.DATABASE_PORT}/{self.DATABASE_NAME}"
        )

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
