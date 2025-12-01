from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Format: postgresql+psycopg://user:password@host/dbname
DATABASE_URL = "postgresql+asyncpg://postgres:postgrespassword@localhost/ferrytracker"
Base = declarative_base()

engine = create_async_engine(DATABASE_URL, echo=True)

AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)  # type: ignore


# Dependency injection function remains the same (still yields the session)
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
