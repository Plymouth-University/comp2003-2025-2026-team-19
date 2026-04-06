from fastapi.testclient import TestClient

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
