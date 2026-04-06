import pytest
from sqlalchemy import text


def test_database_connection(db_session):
    """Verify that the sync db_session can talk to PostGIS."""
    result = db_session.execute(text("SELECT postgis_full_version();"))
    version = result.scalar()
    assert "POSTGIS" in version
    print(f"\n[CONFTEST CHECK] PostGIS Version: {version}")


def test_api_reaches_test_db(client):
    """Verify that the API is using the test override, not production."""
    response = client.get("/health")
    assert response.status_code == 200

    # Verify the app dependency was actually overridden
    from core.database import get_db_session
    from web.api.src.main import app

    assert get_db_session in app.dependency_overrides
