from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Format: postgresql+psycopg://user:password@host/dbname
# DATABASE_URL = "postgresql+asyncpg://postgres:postgrespassword@localhost/ferrytracker"
from .settings import settings

Base = declarative_base(
    metadata=MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )
)

engine = create_async_engine(settings.DATABASE_URL, echo=True)

AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)  # type: ignore


async def get_db_session() -> AsyncSession:  # type: ignore
    async with AsyncSessionLocal() as session:  # type: ignore
        try:
            yield session  # type: ignore
            # SQLAlchemy 2.0+ recommends explicit commit/rollback for async sessions
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
