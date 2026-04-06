import pytest
from fastapi.testclient import TestClient
from sqlalchemy import URL, create_engine
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker
from testcontainers.postgres import PostgresContainer

from core.database import Base, get_db_session
from web.api.src.main import app


# Set up postgis container (persistent across tests)
@pytest.fixture(scope="session")
def postgis_container():
    with PostgresContainer("postgis/postgis:18-3.6-alpine") as postgres:
        yield postgres


@pytest.fixture(scope="session", autouse=True)
def setup_db(postgis_container):
    sync_url = postgis_container.get_connection_url()
    engine = create_engine(sync_url)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture(scope="function")
def db_session(postgis_container):
    engine = create_engine(postgis_container.get_connection_url(), pool_pre_ping=True)

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    session = SessionLocal()

    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def client(postgis_container):
    """
    Async client for FastAPI.
    Overwrites the production async engine with one pointing to the container.
    """
    # Create an async engine pointing to the container
    # Convert 'postgresql://' to 'postgresql+asyncpg://'
    async_url = URL.create(
        drivername="postgresql+asyncpg",
        username=postgis_container.username,
        password=postgis_container.password,
        host=postgis_container.get_container_host_ip(),
        port=postgis_container.get_exposed_port(postgis_container.port),
        database=postgis_container.dbname,
    )
    async_engine_test = create_async_engine(async_url)
    AsyncSessionLocal = async_sessionmaker(async_engine_test, expire_on_commit=False)

    async def override_get_db():
        async with AsyncSessionLocal() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_get_db

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()
