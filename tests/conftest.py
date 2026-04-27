import os

import pytest
import pytest_asyncio
import sentry_sdk
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy import URL, create_engine
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker
from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer

from core.database import Base, get_db_session
from core.settings import settings
from web.api.src.main import app


@pytest.fixture(scope="session")
def redis_container():
    if os.getenv("GITHUB_ACTIONS") == "true":

        class MockContainer:
            def get_container_host_ip(self):
                return "localhost"

            def get_exposed_port(self, port):
                return 6379

        yield MockContainer()
    else:
        with RedisContainer("redis:8.6-alpine") as container:
            yield container


@pytest.fixture(autouse=True)
def override_redis_connection(redis_container, monkeypatch):
    """
    Force settings to use the testcontainer ports.
    """
    test_host = redis_container.get_container_host_ip()
    test_port = redis_container.get_exposed_port(6379)

    monkeypatch.setattr(settings, "REDIS_HOST", test_host)
    monkeypatch.setenv("REDIS_HOST", test_host)


@pytest.fixture(scope="session")
def postgis_container():
    if os.getenv("GITHUB_ACTIONS") == "true":

        class MockContainer:
            username = "ft_admin"
            password = "password"
            dbname = "ferrytracker"
            port = 5432

            def get_container_host_ip(self):
                return "localhost"

            def get_exposed_port(self, port):
                return 5432

            def get_connection_url(self):
                return f"postgresql://{self.username}:{self.password}@{self.get_container_host_ip()}:{self.get_exposed_port(self.port)}/{self.dbname}"

        yield MockContainer()
    else:
        with PostgresContainer("postgis/postgis:18-3.6-alpine") as postgres:
            yield postgres


@pytest.fixture(scope="session", autouse=True)
def disable_sentry():
    """Ensure Sentry is disabled for the duration of the test suite."""
    sentry_sdk.init(dsn="")


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


@pytest_asyncio.fixture
async def db_override(postgis_container, override_redis_connection):
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
    yield
    app.dependency_overrides.clear()


@pytest_asyncio.fixture(autouse=True)
async def clear_database(postgis_container):
    """
    This runs after every single test and wipes all data
    without dropping the tables themselves.
    """
    yield

    # After the test completes:
    sync_url = postgis_container.get_connection_url()
    engine = create_engine(sync_url)

    with engine.connect() as conn:
        trans = conn.begin()
        # Get all table names from your Base metadata
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
        trans.commit()
    engine.dispose()


@pytest_asyncio.fixture
async def async_client(db_override):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
def client(postgis_container, override_redis_connection):
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
