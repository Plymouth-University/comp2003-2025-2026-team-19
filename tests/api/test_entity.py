from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from core import models
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
    assert "value is not a valid uuid" in data["detail"]


def test_list_entities(db_session, client: TestClient):
    # Create multiple test entities
    create_test_entity(db_session, name="Entity 1")
    create_test_entity(db_session, name="Entity 2")

    # Test listing all entities
    response = client.get("/entities")

    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 2  # At least the two we just created
    assert any(entity["name"] == "Entity 1" for entity in data)
    assert any(entity["name"] == "Entity 2" for entity in data)


def test_list_entities_empty(db_session: Session, client: TestClient):
    # Ensure the database is empty
    db_session.query(models.Entity).delete()
    db_session.commit()

    # Test listing entities when there are none
    response = client.get("/entities")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 0
