# database.py (Updated for psycopg)
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# ⚠️ IMPORTANT: Note the dialect: postgresql+psycopg
# Format: postgresql+psycopg://user:password@host/dbname
DATABASE_URL = "postgresql+psycopg://myuser:mypassword@localhost/mydatabase"

# Create the asynchronous engine
# The 'psycopg' dialect supports async directly.
engine = create_async_engine(
    DATABASE_URL,
    echo=True,
    # Optional: Pool settings if needed
    pool_size=20,
    max_overflow=0,
)

# Define the base class for declarative models
Base = declarative_base()

# Configure the sessionmaker for asynchronous use
# This remains the same as before
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)  # type: ignore


# Dependency injection function remains the same (still yields the session)
async def get_db_session() -> AsyncSession:  # type: ignore
    """
    Dependency that yields an AsyncSession for a request.
    """
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
