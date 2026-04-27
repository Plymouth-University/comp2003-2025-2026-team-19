from fastapi.testclient import TestClient

from web.frontend.main import app

client = TestClient(app)


def test_get_status_without_entity_id():
    response = client.get("/status")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_get_status_with_entity_id():
    entity_id = "test_entity"
    response = client.get(f"/status?entity_id={entity_id}")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    # TODO: Verify entity_id is passed to template (requires inspecting response content)


def test_get_root():
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_get_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"message": "Service is healthy"}
