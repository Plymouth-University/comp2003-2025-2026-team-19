from fastapi.testclient import TestClient

from core import database, models
from tests import conftest
from tests.utils import create_test_entity


def test_get_entity_by_uuid(db_session, client: TestClient):
    # Create a test entity
    test_entity = create_test_entity(db_session)

    # Test fetching the entity by UUID
    response = client.get(f"/entities/{test_entity.uuid}")

    assert response.status_code == 200
    data = response.json()
    assert data["uuid"] == str(test_entity.uuid)
    assert data["name"] == test_entity.name


def test_get_entity_by_uuid_not_found(client: TestClient):
    # Test fetching an entity with a non-existent UUID
    response = client.get("/entities/00000000-0000-0000-0000-000000000000")

    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == "Entity not found"


def test_get_entity_by_uuid_invalid_uuid(client: TestClient):
    # Test fetching an entity with an invalid UUID format
    response = client.get("/entities/invalid-uuid")

    assert response.status_code == 422
    data = response.json()
    assert "value is not a valid uuid" in data["detail"][0]["msg"]
