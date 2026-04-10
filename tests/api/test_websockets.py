import asyncio

import anyio
import pytest
from fastapi import WebSocketDisconnect
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from httpx_ws import WebSocketDisconnect, aconnect_ws

from core import models
from tests.utils import create_test_entity
from web.api.src.main import app


def test_websocket_subscription(db_session, client: TestClient):
    entity = create_test_entity(db_session)

    with client.websocket_connect("/entities/ws") as websocket:
        websocket.send_json({"action": "subscribe", "entity_ids": [str(entity.uuid)]})

        msg = websocket.receive_json()
        assert msg["status"] == "subscribed"
        assert str(entity.uuid) in msg["entities"]
        assert msg["entities"][str(entity.uuid)]["name"] == entity.name


def test_websocket_subscription_invalid_entity(db_session, client: TestClient):
    with client.websocket_connect("/entities/ws") as websocket:
        websocket.send_json(
            {
                "action": "subscribe",
                "entity_ids": ["00000000-0000-0000-0000-000000000000"],
            }
        )

        msg = websocket.receive_json()
        assert msg["status"] == "subscribed"
        assert "00000000-0000-0000-0000-000000000000" not in msg["entities"]


def test_websocket_subscription_no_entity_ids(client: TestClient):
    with client.websocket_connect("/entities/ws") as websocket:
        websocket.send_json({"action": "subscribe"})

        msg = websocket.receive_json()
        assert msg["status"] == "subscribed"
        assert msg["entities"] == {}


@pytest.mark.xfail(reason="Server logic not yet implemented", strict=True)
@pytest.mark.anyio
async def test_websocket_subscription_invalid_action(async_client):
    async with aconnect_ws("/entities/ws", async_client) as websocket:
        await websocket.send_json({"action": "invalid"})
        data = await asyncio.wait_for(websocket.receive_json(), timeout=5)


@pytest.mark.xfail(reason="Server logic not yet implemented", strict=True)
@pytest.mark.anyio
async def test_websocket_subscription_malformed_message(async_client):
    async with aconnect_ws("/entities/ws", async_client) as websocket:
        await websocket.send_text("This is not a valid JSON message")
        with pytest.raises(WebSocketDisconnect) as exc:
            await asyncio.wait_for(websocket.receive_json(), timeout=5)
        assert exc.value.code in [1003, 1007]


@pytest.mark.xfail(reason="Server logic not yet implemented", strict=True)
@pytest.mark.anyio
async def test_websocket_subscription_missing_action(async_client):
    async with aconnect_ws("/entities/ws", async_client) as websocket:
        await websocket.send_json({"entity_ids": ["some-entity-id"]})
        with pytest.raises(WebSocketDisconnect) as exc:
            await asyncio.wait_for(websocket.receive_json(), timeout=5)
        assert exc.value.code == 1008


@pytest.mark.xfail(reason="Server logic not yet implemented", strict=True)
@pytest.mark.anyio
async def test_websocket_subscription_invalid_entity_format(async_client):
    async with aconnect_ws("/entities/ws", async_client) as websocket:
        await websocket.send_json({"action": "subscribe", "entity_ids": 12345})
        with pytest.raises(WebSocketDisconnect) as exc:
            await asyncio.wait_for(websocket.receive_json(), timeout=5)
        assert exc.value.code == 1008
